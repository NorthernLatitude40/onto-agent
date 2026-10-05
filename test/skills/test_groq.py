import os
import unittest
from groq import Groq


class TestGroqModels(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """初始化 Groq 客戶端"""
        cls.api_key = os.getenv("GROQ_API_KEY")
        if not cls.api_key:
            raise unittest.SkipTest("未偵測到 GROQ_API_KEY 環境變數，跳過測試")
        
        cls.client = Groq(api_key=cls.api_key)

    def test_list_models(self):
        """測試獲取 Groq 模型清單並印出可用 Model ID"""
        response = self.client.models.list()
        
        # 斷言回傳結果包含資料
        self.assertIsNotNone(response.data, "Groq API 回傳的 models 列表為空")
        self.assertGreater(len(response.data), 0, "當前帳號未獲取到任何可用的 Groq 模型")

        print("\n" + "=" * 10 + " 當前帳號可用的 Groq 模型清單 " + "=" * 10)
        active_models = []
        for model in response.data:
            model_id = model.id
            active_models.append(model_id)
            print(f"- {model_id}")
        print("=" * 46)

        # 斷言回傳的模型 ID 均為非空字串
        for model_id in active_models:
            self.assertTrue(isinstance(model_id, str) and len(model_id) > 0)


if __name__ == "__main__":
    unittest.main()