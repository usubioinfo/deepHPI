import net from "node:net";
import { spawn } from "node:child_process";
import process from "node:process";

function findFreePort(start, end) {
  return new Promise((resolve, reject) => {
    const tryPort = (port) => {
      if (port > end) {
        reject(new Error(`No free port found in range ${start}-${end}.`));
        return;
      }

      const server = net.createServer();
      server.unref();
      server.on("error", () => tryPort(port + 1));
      server.listen(port, "127.0.0.1", () => {
        const { port: freePort } = server.address();
        server.close(() => resolve(freePort));
      });
    };

    tryPort(start);
  });
}

const backendPort = await findFreePort(8000, 8020);
const frontendPort = Number(process.env.DEEPHPI_UI_PORT || 5173);

const pythonEnv = {
  ...process.env,
  DEEPHPI_PORT: String(backendPort),
};

const viteEnv = {
  ...process.env,
  VITE_API_BASE: `http://127.0.0.1:${backendPort}`,
};

const python = spawn("python3", ["server/app.py"], {
  cwd: process.cwd(),
  env: pythonEnv,
  stdio: "inherit",
});

const vite = spawn("npx", ["vite", "--host", "127.0.0.1", "--port", String(frontendPort)], {
  cwd: process.cwd(),
  env: viteEnv,
  stdio: "inherit",
});

const shutdown = (code = 0) => {
  python.kill("SIGTERM");
  vite.kill("SIGTERM");
  process.exit(code);
};

python.on("exit", (code) => {
  if (code && code !== 0) {
    shutdown(code);
  }
});

vite.on("exit", (code) => {
  if (code && code !== 0) {
    shutdown(code);
  }
});

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

console.log(`DeepHPI dev mode`);
console.log(`API: http://127.0.0.1:${backendPort}`);
console.log(`UI:  http://127.0.0.1:${frontendPort}`);
