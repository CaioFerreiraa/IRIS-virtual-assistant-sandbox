"use strict";

const fs = require("fs");
const http = require("http");
const path = require("path");
const { URL } = require("url");

const HOST = "127.0.0.1";
const DEFAULT_PORT = 8765;
const MAX_BODY_BYTES = 16 * 1024;
const MAX_NOTE_LENGTH = 500;
const INDEX_PATH = path.join(__dirname, "public", "index.html");

const configuredPort = Number.parseInt(process.env.IRIS_NOTES_PORT || "", 10);
const port = Number.isInteger(configuredPort) && configuredPort > 0 && configuredPort <= 65535
    ? configuredPort
    : DEFAULT_PORT;

const notes = [];
let nextId = 1;

class RequestError extends Error {
    constructor(statusCode, message) {
        super(message);
        this.statusCode = statusCode;
    }
}

function sendJson(response, statusCode, payload, extraHeaders = {}) {
    const content = Buffer.from(JSON.stringify(payload), "utf8");
    response.writeHead(statusCode, {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Length": content.length,
        ...extraHeaders,
    });
    response.end(content);
}

function sendMethodNotAllowed(response, allowedMethods) {
    sendJson(
        response,
        405,
        { success: false, message: "Método não permitido." },
        { Allow: allowedMethods.join(", ") },
    );
}

function readJsonBody(request) {
    return new Promise((resolve, reject) => {
        const chunks = [];
        let receivedBytes = 0;
        let settled = false;

        function fail(error) {
            if (settled) {
                return;
            }
            settled = true;
            reject(error);
        }

        request.on("data", (chunk) => {
            receivedBytes += chunk.length;
            if (receivedBytes > MAX_BODY_BYTES) {
                fail(new RequestError(413, "O corpo da requisição excede o limite permitido."));
                return;
            }
            chunks.push(chunk);
        });
        request.on("end", () => {
            if (settled) {
                return;
            }
            settled = true;
            if (receivedBytes === 0) {
                reject(new RequestError(400, "O corpo JSON é obrigatório."));
                return;
            }
            try {
                const value = JSON.parse(Buffer.concat(chunks).toString("utf8"));
                if (value === null || Array.isArray(value) || typeof value !== "object") {
                    reject(new RequestError(400, "O corpo JSON deve ser um objeto."));
                    return;
                }
                resolve(value);
            } catch (_) {
                reject(new RequestError(400, "O corpo deve conter JSON válido."));
            }
        });
        request.on("error", () => {
            fail(new RequestError(400, "Não foi possível ler o corpo da requisição."));
        });
    });
}

function validatedText(payload) {
    if (!Object.prototype.hasOwnProperty.call(payload, "text")) {
        throw new RequestError(400, "O campo 'text' é obrigatório.");
    }
    if (typeof payload.text !== "string") {
        throw new RequestError(400, "O campo 'text' deve ser uma string.");
    }
    const text = payload.text.trim();
    if (!text) {
        throw new RequestError(400, "O texto da nota não pode ficar vazio.");
    }
    if (text.length > MAX_NOTE_LENGTH) {
        throw new RequestError(400, "O texto da nota deve possuir no máximo 500 caracteres.");
    }
    return text;
}

function validatedId(rawId) {
    if (!/^[1-9]\d*$/.test(rawId)) {
        throw new RequestError(400, "O ID da nota é inválido.");
    }
    const id = Number(rawId);
    if (!Number.isSafeInteger(id)) {
        throw new RequestError(400, "O ID da nota é inválido.");
    }
    return id;
}

function findNoteIndex(id) {
    return notes.findIndex((note) => note.id === id);
}

async function handleRequest(request, response) {
    const requestUrl = new URL(request.url, `http://${HOST}:${port}`);
    const pathname = requestUrl.pathname;

    if (pathname === "/health") {
        if (request.method !== "GET") {
            sendMethodNotAllowed(response, ["GET"]);
            return;
        }
        sendJson(response, 200, {
            success: true,
            message: "O serviço de notas está online.",
        });
        return;
    }

    if (pathname === "/") {
        if (request.method !== "GET") {
            sendMethodNotAllowed(response, ["GET"]);
            return;
        }
        const html = await fs.promises.readFile(INDEX_PATH);
        response.writeHead(200, {
            "Content-Type": "text/html; charset=utf-8",
            "Content-Length": html.length,
        });
        response.end(html);
        return;
    }

    if (pathname === "/api/notes") {
        if (request.method === "GET") {
            sendJson(response, 200, {
                success: true,
                message: "Notas carregadas com sucesso.",
                data: notes,
            });
            return;
        }
        if (request.method === "POST") {
            const payload = await readJsonBody(request);
            const note = { id: nextId, text: validatedText(payload) };
            nextId += 1;
            notes.push(note);
            sendJson(response, 201, {
                success: true,
                message: "Nota criada com sucesso.",
                data: note,
            });
            return;
        }
        sendMethodNotAllowed(response, ["GET", "POST"]);
        return;
    }

    const noteMatch = pathname.match(/^\/api\/notes\/([^/]+)$/);
    if (noteMatch) {
        if (request.method !== "PUT" && request.method !== "DELETE") {
            sendMethodNotAllowed(response, ["PUT", "DELETE"]);
            return;
        }
        const id = validatedId(noteMatch[1]);
        const noteIndex = findNoteIndex(id);
        if (noteIndex < 0) {
            throw new RequestError(404, "Nota não encontrada.");
        }

        if (request.method === "PUT") {
            const payload = await readJsonBody(request);
            notes[noteIndex].text = validatedText(payload);
            sendJson(response, 200, {
                success: true,
                message: "Nota atualizada com sucesso.",
                data: notes[noteIndex],
            });
            return;
        }

        const deletedNote = notes.splice(noteIndex, 1)[0];
        sendJson(response, 200, {
            success: true,
            message: "Nota excluída com sucesso.",
            data: deletedNote,
        });
        return;
    }

    sendJson(response, 404, {
        success: false,
        message: "Rota não encontrada.",
    });
}

const server = http.createServer((request, response) => {
    handleRequest(request, response).catch((error) => {
        if (response.headersSent) {
            response.end();
            return;
        }
        if (error instanceof RequestError) {
            sendJson(response, error.statusCode, {
                success: false,
                message: error.message,
            });
            return;
        }
        console.error("Erro inesperado no backend do módulo Notas.");
        sendJson(response, 500, {
            success: false,
            message: "Não foi possível processar a solicitação.",
        });
    });
});

server.requestTimeout = 10_000;
server.headersTimeout = 12_000;

function shutdown() {
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(1), 3_000).unref();
}

process.once("SIGTERM", shutdown);
process.once("SIGINT", shutdown);

server.on("error", () => {
    console.error("Não foi possível iniciar o backend do módulo Notas.");
    process.exit(1);
});

server.listen(port, HOST, () => {
    console.log(`Backend do módulo Notas disponível em http://${HOST}:${port}.`);
});
