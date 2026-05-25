# LM Studio Setup — Remote LLM Server (ai.amirulaliff.com)

This guide covers setting up LM Studio on the remote machine to serve the Gemma 3 4B model for the OCR pipeline's Stage 2.

---

## 1. Install LM Studio

Download from [lmstudio.ai](https://lmstudio.ai) and install on the remote machine (Windows/Mac/Linux).

## 2. Load the Model

1. Open LM Studio
2. Go to the **Search** tab (magnifying glass icon)
3. Search for **`gemma-3-4b-it`** (Google's Gemma 3 4B Instruct)
4. Click **Download**
5. Once downloaded, load it via the **Chat** tab

> **Why Gemma 3 4B?** Excellent instruction-following and JSON output at just 4B parameters — runs comfortably on CPU or low-end GPUs. If the 4B model struggles with complex multi-page resumes, you can swap to a larger model like Llama 3.1 8B or Mistral 7B — just update the `LM_STUDIO_MODEL` env var.

## 3. Start the Local Server

1. Go to the **Local Server** tab in LM Studio (the `</>` icon)
2. Select the loaded `gemma-3-4b-it` model
3. Set **Port** to `1234`
4. Click **Start Server**

LM Studio now exposes an OpenAI-compatible API at:

```
http://ai.amirulaliff.com:1234/v1
```

## 4. Verify It Works

From the OCR pipeline machine, test the endpoint:

```bash
curl http://ai.amirulaliff.com:1234/v1/models
```

Expected response:
```json
{
  "data": [
    {
      "id": "gemma-3-4b-it",
      ...
    }
  ]
}
```

Test a quick completion:

```bash
curl http://ai.amirulaliff.com:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma-3-4b-it",
    "messages": [{"role": "user", "content": "Say hello in JSON: {\"greeting\": \"...\"}"}],
    "response_format": {"type": "json_object"}
  }'
```

## 5. Network Access (if on different machine)

If the OCR pipeline runs on a different machine:

- **Windows**: Make sure LM Studio is allowed through Windows Firewall (port 1234)
- **Same LAN**: Access via LAN IP if `ai.amirulaliff.com` doesn't resolve
- **Tailscale/Zerotier**: Use the VPN IP for secure remote access

## 6. Model Recommendations

| Model | Size | RAM Needed | Notes |
|-------|------|------------|-------|
| **gemma-3-4b-it** (default) | ~2.5 GB | 4-6 GB | Best quality-to-size ratio for JSON extraction |
| llama-3.2-3b-instruct | ~2 GB | 3-4 GB | Faster, slightly less precise |
| llama-3.1-8b-instruct | ~5 GB | 8-10 GB | Better on complex multi-column resumes |
| qwen2.5-7b-instruct | ~4.5 GB | 6-8 GB | Strong alternative, good at structured output |

To switch models, set the env var when starting the pipeline server:

```bash
LM_STUDIO_MODEL=llama-3.1-8b-instruct uvicorn pipeline.server:app
```
