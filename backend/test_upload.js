import fs from "fs";
import path from "path";
import fetch from "node-fetch";
import FormData from "form-data";

const TEST_FILE_PATH = "../example_pdf.pdf";

async function runTest() {
  if (!fs.existsSync(TEST_FILE_PATH)) {
    console.error(`Please put a test PDF at: ${path.resolve(TEST_FILE_PATH)}`);
    process.exit(1);
  }
  
  console.log("Sending file directly to Gateway API on port 3000...");
  const form = new FormData();
  form.append("file", fs.createReadStream(TEST_FILE_PATH));

  try {
    const res = await fetch("http://localhost:3000/api/pdf/analyze", {
      method: "POST",
      body: form
    });
    const result = await res.json();
    if (res.ok && result.success) {
      console.log("SUCCESS!");
      console.log(`Total Pages: ${result.data.total_pages}`);
      console.log("First 3 detected text blocks on Page 1:");
      console.log(result.data.pages[0].texts.slice(0, 3));
    } else {
      console.error("FAILED:", result);
    }
  } catch (err) {
    console.error("Error connecting to API:", err.message);
  }
}

runTest();
