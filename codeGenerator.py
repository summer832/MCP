import re
import subprocess
import tempfile
import time
from typing import Optional, Tuple
from openai import OpenAI

class DatabaseCodeGenerator:
    def __init__(self):
        # 确保 API Key 正确配置
        self.api_key = "sk-plGxjDmsvzQZAHZeA06flzwdlhdFsLZORvvhNKeJ2M9e65Ls"  # 替换为你的实际 API Key
        self.client = OpenAI(
            api_key=self.api_key,  # 确保 API Key 正确传递
            base_url="https://api.moonshot.cn/v1"  # Moonshot AI 的 API 地址
        )
        self.max_retries = 3  # 最大重试次数
        self.api_call_count = 0  # API 调用计数器
        self.last_api_call_time = 0  # 上次 API 调用时间

    def generate_and_test(self, requirement: str) -> str:
        """主工作流程：生成并测试数据库代码"""
        for attempt in range(self.max_retries):
            print(f"\n=== 尝试第 {attempt+1} 次 ===")
            
            # 生成或修正代码
            if attempt == 0:
                code = self._generate_initial_code(requirement)
            else:
                code = self._generate_fix_code(requirement, error_log)
                
            print(f"\n生成的代码：\n{code}")
            
            # 执行测试
            test_result, error_log = self._execute_with_tests(code)
            
            if test_result:
                return code
                
            # 保存错误日志
            if attempt == self.max_retries - 1:
                self._save_error_log(code, error_log)
                return f"// 无法通过测试，错误日志已保存"
                
        return f"// 无法通过测试，最终错误：\n{error_log}"

    def _generate_initial_code(self, requirement: str) -> str:
        """生成初始数据库代码"""
        prompt = f"根据以下查询生成TypeScript代码,能在本地数据库中执行对应的操作,除了代码外不需要任何其他内容！除了代码不生成任何其他内容：\n\n查询: {requirement}\n\n代码:"
        return self._get_llm_response(prompt)

    def _generate_fix_code(self, requirement: str, error: str) -> str:
        """生成修复代码"""
        prompt = f"请修复以下TypeScript代码的错误：\n\n原始需求：{requirement}\n\n错误信息：{error}\n\n修复后的代码："
        return self._get_llm_response(prompt)

    def _get_llm_response(self, prompt: str) -> str:
        """获取大模型响应，带频率限制"""
        # 检查调用频率
        current_time = time.time()
        if self.api_call_count >= 3 and current_time - self.last_api_call_time < 60:
            raise Exception("API 调用频率超限，请稍后再试")

        try:
            # 调用 Moonshot AI API
            response = self.client.chat.completions.create(
                model="moonshot-v1-8k",  # 使用 Moonshot 的模型
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500
            )
            
            # 更新调用状态
            self.api_call_count += 1
            self.last_api_call_time = current_time
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"API 调用失败: {e}")
            raise Exception(f"API 调用失败，请检查 API Key 和网络连接: {e}")

    def _execute_with_tests(self, code: str) -> Tuple[bool, str]:
        """执行测试"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ts", delete=False) as f:
            f.write(self._add_test_harness(code))
            file_path = f.name

        try:
            # 使用 ts-node 执行测试
            result = subprocess.run(
                ["ts-node", file_path],
                capture_output=True,
                text=True,
                timeout=30,
                check=False
            )
            
            # 分析测试结果
            if result.returncode == 0:
                print("\n✅ 所有测试通过")
                return True, ""
                
            error_msg = self._parse_test_errors(result.stderr)
            print(f"\n❌ 测试失败：{error_msg}")
            return False, error_msg
            
        except subprocess.TimeoutExpired:
            return False, "执行超时"
        finally:
            subprocess.run(["rm", file_path])

    def _add_test_harness(self, code: str) -> str:
        """添加测试框架"""
        test_code = """
// 确保安装 dotenv 和 mysql2
import mysql from 'mysql2/promise';
import dotenv from 'dotenv';

dotenv.config();
"""
        return code.replace("import mysql", test_code)

    def _parse_test_errors(self, stderr: str) -> str:
        """解析测试错误"""
        error_lines = [line for line in stderr.split('\n') if 'Error:' in line]
        return '\n'.join(error_lines[-3:]) if error_lines else "未知错误"

    def _save_error_log(self, code: str, error: str) -> None:
        """保存错误日志"""
        with open("error_log.txt", "w") as f:
            f.write(f"=== 生成的代码 ===\n{code}\n\n")
            f.write(f"=== 错误信息 ===\n{error}\n")
        print("错误日志已保存到 error_log.txt")

# 使用示例
if __name__ == "__main__":
    generator = DatabaseCodeGenerator()
    
    requirement = """
    实现一个学生管理系统，要求：
    1. 创建 students 表（id, name, age）
    2. 实现学生注册功能
    3. 实现按年龄查询学生
    4. 包含测试用例
    """
    
    final_code = generator.generate_and_test(requirement)
    print("\n最终代码：")
    print(final_code)