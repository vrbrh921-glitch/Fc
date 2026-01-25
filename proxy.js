const cluster = require('cluster');

if (cluster.isMaster) {
  function startWorker() {
    const worker = cluster.fork();
    worker.on('exit', (code, signal) => {
      console.log(Worker exited (code: ${code}, signal: ${signal}). Restarting...);
      setTimeout(startWorker, 100); // restart quickly
    });
  }
  startWorker();
} else {
  // Put your proxy server code here
  const http = require('http');
  const net = require('net');
  const url = require('url');

  const server = http.createServer((req, res) => {
    const target = url.parse(req.url);

    const proxyReq = http.request({
      hostname: target.hostname,
      port: target.port || 80,
      path: target.path,
      method: req.method,
      headers: req.headers
    }, proxyRes => {
      res.writeHead(proxyRes.statusCode, proxyRes.headers);
      proxyRes.pipe(res);
    });

    req.pipe(proxyReq);
  });

  server.on('connect', (req, clientSocket, head) => {
    const [host, port] = req.url.split(':');

    const serverSocket = net.connect(port || 443, host, () => {
      clientSocket.write(
        'HTTP/1.1 200 Connection Established\r\n\r\n'
      );
      serverSocket.write(head);
      serverSocket.pipe(clientSocket);
      clientSocket.pipe(serverSocket);
    });
  });

  server.listen(8888, () => {
    console.log('Proxy listening on 127.0.0.1:8888');
  });
}
