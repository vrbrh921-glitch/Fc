const cluster = require('cluster');
const os = require('os');
const https = require('https');
const http = require('http');
const net = require('net');
const url = require('url');
const forge = require('node-forge');

const HOST = '0.0.0.0';
const PORT = 8888;
const WORKERS = Math.min(2, os.cpus().length || 1);

if (cluster.isMaster) {
  console.log(`Master ${process.pid} starting — generating cert once`);

  // Generate RSA key + cert ONCE
  forge.pki.rsa.generateKeyPair({ bits: 2048, workers: 2 }, (err, keys) => {
    if (err) {
      console.error(err);
      process.exit(1);
    }

    const cert = forge.pki.createCertificate();
    cert.publicKey = keys.publicKey;
    cert.serialNumber = '01';
    cert.validity.notBefore = new Date();
    cert.validity.notAfter = new Date();
    cert.validity.notAfter.setFullYear(cert.validity.notBefore.getFullYear() + 2);

    const attrs = [{ name: 'commonName', value: 'HTTPS Proxy' }];
    cert.setSubject(attrs);
    cert.setIssuer(attrs);
    cert.sign(keys.privateKey);

    const TLS_KEY = forge.pki.privateKeyToPem(keys.privateKey);
    const TLS_CERT = forge.pki.certificateToPem(cert);

    for (let i = 0; i < WORKERS; i++) {
      cluster.fork({ TLS_KEY, TLS_CERT });
    }

    cluster.on('exit', () => {
      console.log('Worker died → restarting');
      cluster.fork({ TLS_KEY, TLS_CERT });
    });
  });

} else {
  const server = https.createServer({
    key: process.env.TLS_KEY,
    cert: process.env.TLS_CERT
  }, (req, res) => {
    const parsed = url.parse(req.url);

    if (!parsed.hostname) {
      res.writeHead(400);
      return res.end('Bad Request');
    }

    const isHttps = parsed.protocol === 'https:';
    const proxy = isHttps ? https : http;

    const proxyReq = proxy.request({
      hostname: parsed.hostname,
      port: parsed.port || (isHttps ? 443 : 80),
      path: parsed.path,
      method: req.method,
      headers: req.headers,
      rejectUnauthorized: false
    }, proxyRes => {
      res.writeHead(proxyRes.statusCode, proxyRes.headers);
      proxyRes.pipe(res);
    });

    proxyReq.on('error', () => {
      res.writeHead(502);
      res.end();
    });

    req.pipe(proxyReq);
  });

  // HTTPS CONNECT tunnel
  server.on('connect', (req, clientSocket, head) => {
    const [host, port] = req.url.split(':');
    const serverSocket = net.connect(port || 443, host, () => {
      clientSocket.write(
        'HTTP/1.1 200 Connection Established\r\n\r\n'
      );
      if (head.length) serverSocket.write(head);
      serverSocket.pipe(clientSocket);
      clientSocket.pipe(serverSocket);
    });

    serverSocket.on('error', () => clientSocket.end());
  });

  server.listen(PORT, HOST, () => {
    console.log(`Worker ${process.pid} HTTPS proxy → https://${HOST}:${PORT}`);
  });

  process.on('uncaughtException', () => process.exit(1));
  process.on('unhandledRejection', () => process.exit(1));
                            }
