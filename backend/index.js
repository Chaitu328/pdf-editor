import express from "express";
import cors from "cors";
import multer from "multer";
import fetch from "node-fetch";
import FormData from "form-data";
import dotenv from "dotenv";

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;
const PDF_SERVICE_URL = process.env.PDF_SERVICE_URL || "http://127.0.0.1:8000";
const PDF_SERVICE_API_KEY = process.env.PDF_SERVICE_API_KEY || "";

app.use(cors());
app.use(express.json());

const storage = multer.memoryStorage();
const upload = multer({ 
  storage, 
  limits: { fileSize: 25 * 1024 * 1024 }
});

const callPythonService = async (method, endpoint, body = null, headers = {}) => {
  const url = `${PDF_SERVICE_URL}${endpoint}`;
  const defaultHeaders = {
    "x-api-key": PDF_SERVICE_API_KEY,
    ...headers,
  };
  const options = { method, headers: defaultHeaders };
  if (body && method !== "GET") {
    if (body instanceof FormData) {
      options.body = body;
    } else {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
  }
  return fetch(url, options);
};

app.post("/api/pdf/analyze", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ success: false, error: "No file uploaded" });
    }
    const form = new FormData();
    form.append("file", req.file.buffer, {
      filename: req.file.originalname,
      contentType: req.file.mimetype,
    });
    console.log(`[Proxy] Forwarding upload to Python: ${req.file.originalname}`);
    const response = await callPythonService("POST", "/pdf/analyze", form, form.getHeaders());
    if (!response.ok) {
      const errText = await response.text();
      return res.status(response.status).json({ success: false, error: errText });
    }
    const result = await response.json();
    return res.json(result);
  } catch (error) {
    console.error("Analyze Error:", error);
    return res.status(500).json({ success: false, error: error.message });
  }
});

app.post("/api/pdf/apply-edits", async (req, res) => {
  try {
    console.log("[Proxy] Forwarding apply-edits request to Python");
    const response = await callPythonService("POST", "/pdf/apply-edits", req.body);
    if (!response.ok) {
      const errText = await response.text();
      return res.status(response.status).json({ success: false, error: errText });
    }
    const result = await response.json();
    return res.json(result);
  } catch (error) {
    console.error("Apply Edits Error:", error);
    return res.status(500).json({ success: false, error: error.message });
  }
});

app.get("/api/pdf/download", async (req, res) => {
  try {
    const { path } = req.query;
    if (!path) {
      return res.status(400).json({ success: false, error: "File path is required" });
    }
    console.log(`[Proxy] Requesting download for: ${path}`);
    const response = await callPythonService("GET", `/pdf/download?path=${encodeURIComponent(path)}`);
    if (!response.ok) {
      const errText = await response.text();
      return res.status(response.status).json({ success: false, error: errText });
    }
    res.setHeader("Content-Type", "application/pdf");
    res.setHeader("Content-Disposition", `attachment; filename="${path.split('/').pop() || 'edited.pdf'}"`);
    response.body.pipe(res);
  } catch (error) {
    console.error("Download Error:", error);
    return res.status(500).json({ success: false, error: error.message });
  }
});

app.get("/api/health", (req, res) => {
  res.json({ success: true, status: "running", service: "pdf-gateway" });
});

app.listen(PORT, () => {
  console.log(`[Server] Node.js PDF Editor Gateway running on http://localhost:${PORT}`);
});
