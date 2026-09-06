import modal

# 1. 定义应用名称
app = modal.App("qwen2.5-7b-awq-service")

# 2. 持久化存储卷（用于缓存模型权重，避免重复下载）
hf_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=True)

# 3. 定义容器镜像：使用包含 CUDA NVCC 开发环境的 NVIDIA 官方镜像
image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.1.1-devel-ubuntu22.04", add_python="3.11"
    )
    .env(
        {
            "VLLM_USE_V1": "0",                  # 强制使用稳定的 V0 引擎
            "VLLM_USE_FLASHINFER_SAMPLER": "0",  # 禁用 FlashInfer JIT 采样，避免寻找 NVCC 导致报错
        }
    )
    .pip_install("vllm>=0.6.0", "huggingface_hub")
)

MODEL_ID = "Qwen/Qwen2.5-7B-Instruct-AWQ"


# 4. 定义 LLM 服务类
@app.cls(
    gpu="A10G",
    image=image,
    volumes={"/root/.cache/huggingface": hf_cache},
    timeout=600,
)
class QwenModel:

    @modal.enter()
    def load_model(self):
        from vllm import LLM, SamplingParams  # type: ignore

        print(f"Loading model: {MODEL_ID}...")
        self.llm = LLM(
            model=MODEL_ID,
            quantization="awq",
            max_model_len=4096,
            gpu_memory_utilization=0.90,
            trust_remote_code=True,
            enforce_eager=True,  # 开启 Eager 模式，跳过 CUDA Graph 预热
        )
        self.SamplingParams = SamplingParams
        print("Model loaded successfully!")

    @modal.method()
    def generate(
        self, prompt: str, max_tokens: int = 512, temperature: float = 0.7
    ) -> str:
        """提供给 Python 代码/其他 Modal App 调用的方法"""
        sampling_params = self.SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            repetition_penalty=1.1,         # 增加重复惩罚，防止反复生成 Hashtag
            stop_token_ids=[151643, 151645]  # Qwen2.5 专属 <|endoftext|> 与 <|im_end|> Token ID
        )
        outputs = self.llm.generate([prompt], sampling_params)
        return outputs[0].outputs[0].text

    @modal.fastapi_endpoint(method="POST")
    def api(self, request: dict):
        """暴露给外部调用的 HTTP POST 接口"""
        prompt = request.get("prompt", "")
        max_tokens = request.get("max_tokens", 512)
        temperature = request.get("temperature", 0.7)

        if not prompt:
            return {"error": "prompt is required"}, 400

        sampling_params = self.SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            repetition_penalty=1.1,         # 增加重复惩罚
            stop_token_ids=[151643, 151645]  # 设置明确的停止符
        )
        outputs = self.llm.generate([prompt], sampling_params)
        generated_text = outputs[0].outputs[0].text

        return {"model": MODEL_ID, "response": generated_text}


# 5. 本地测试入口
@app.local_entrypoint()
def main():
    model = QwenModel()
    print("Sending test request to Modal cloud...")
    response = model.generate.remote("请用三句话介绍一下 Python 的优势。")
    print("\n--- 测试生成结果 ---")
    print(response)