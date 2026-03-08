from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_SEED_PATH = Path("scripts/training/data/docqa_workspace/annotations/local_docqa_seed_v1.json")

ANNOTATION_OVERRIDES: dict[str, dict[str, Any]] = {
    "README-answerable-001": {
        "question": "当前本地原始文档目录支持放入哪些文件类型？",
        "expected_answer_points": [
            "pdf",
            "md",
            "docx/doc",
            "txt",
            "csv/tsv",
            "json/jsonl",
            "html/xml",
        ],
    },
    "README-rejectable-001": {
        "question": "工作流说明里是否给出了自动下载私有 Hugging Face 数据集的配置方法？",
    },
    "第一章_初识智能体-answerable-001": {
        "question": "本章会从哪些方面带读者初步认识智能体？",
        "expected_answer_points": [
            "智能体是什么",
            "智能体有哪些主要类型",
            "智能体如何与环境交互",
        ],
    },
    "第一章_初识智能体-answerable-002": {
        "question": "智能体的定义包含哪些关键要素？",
        "expected_answer_points": [
            "通过传感器感知环境",
            "通过执行器采取行动",
            "具有自主性",
            "以达成特定目标为导向",
        ],
    },
    "第一章_初识智能体-answerable-003": {
        "question": "传统视角下的智能体大致经历了怎样的演进路线？",
        "expected_answer_points": [
            "从简单反射智能体起步",
            "发展出需要内部状态的智能体",
            "进一步走向目标/效用驱动与学习型智能体",
        ],
    },
    "第一章_初识智能体-rejectable-001": {
        "question": "本章是否给出了某个开源智能体框架的完整 GitHub 仓库地址？",
    },
    "第七章_构建你的Agent框架-answerable-001": {
        "question": "第七章为什么要从零开始构建 HelloAgents 框架？",
        "expected_answer_points": [
            "从零开始逐步构建 HelloAgents",
            "按版本迭代推进学习与开发",
            "为后续高级应用案例提供统一基础",
        ],
    },
    "第七章_构建你的Agent框架-answerable-002": {
        "question": "为什么仍然需要自建 Agent 框架？",
        "expected_answer_points": [
            "现有框架过度抽象且学习曲线陡峭",
            "API 快速迭代带来不稳定性",
            "黑盒封装影响理解与深度定制",
            "复杂依赖会增加维护成本",
        ],
    },
    "第七章_构建你的Agent框架-answerable-003": {
        "question": "HelloAgents 框架的设计理念是什么？",
        "expected_answer_points": [
            "兼顾轻量级与教学友好",
            "保持高可读性与易理解性",
            "基于标准 API 做务实选择",
            "在功能完整性和学习友好性之间平衡",
        ],
    },
    "第七章_构建你的Agent框架-rejectable-001": {
        "question": "文中是否给出了 HelloAgents 在 Windows 上的官方安装包下载链接？",
    },
    "第三章_大语言模型基础-answerable-001": {
        "question": "第三章主要聚焦什么核心问题？",
        "expected_answer_points": [
            "现代智能体是如何工作的",
            "从语言模型的基本定义讲起",
            "为理解 LLM 的知识与推理能力打基础",
        ],
    },
    "第三章_大语言模型基础-answerable-002": {
        "question": "从 N-gram 到 RNN 的演进说明了什么？",
        "expected_answer_points": [
            "语言模型的任务是计算词序列概率",
            "N-gram 依赖条件概率连乘和马尔可夫假设",
            "RNN 用连续表示建模更长上下文",
        ],
    },
    "第三章_大语言模型基础-answerable-003": {
        "question": "讲解统计语言模型时使用的示例语料库是什么？",
        "expected_answer_points": [
            "datawhale agent learns datawhale agent works",
            "通过 corpus.split() 得到 tokens",
            "使用 len(tokens) 统计总词数",
        ],
    },
    "第三章_大语言模型基础-rejectable-001": {
        "question": "本章是否给出了 Transformer 预训练所需的具体 GPU 价格清单？",
    },
    "第九章_上下文工程-answerable-001": {
        "question": "上下文工程这一章主要讨论哪些问题？",
        "expected_answer_points": [
            "什么是上下文工程",
            "为什么上下文工程重要",
            "如何在 HelloAgents 中实践上下文管理",
        ],
    },
    "第九章_上下文工程-answerable-002": {
        "question": "什么是上下文工程？",
        "expected_answer_points": [
            "关注模型推理时可见的整体上下文",
            "目标是优化进入上下文窗口的信息集合",
            "不只写提示词而是管理整个上下文状态",
        ],
    },
    "第九章_上下文工程-answerable-003": {
        "question": "为什么上下文工程重要？",
        "expected_answer_points": [
            "上下文是一种有限资源",
            "长上下文会出现 context rot",
            "需要谨慎筛选信息以保持检索和推理效果",
        ],
    },
    "第九章_上下文工程-rejectable-001": {
        "question": "文中是否给出了 ContextBuilder 的完整线上 API 文档地址？",
    },
    "第二章_智能体发展史-answerable-001": {
        "question": "第二章是如何梳理智能体发展历史的？",
        "expected_answer_points": [
            "从符号与逻辑的早期范式讲起",
            "经历从单一集中式到协作式智能思想的转变",
            "理解学习范式如何催生现代智能体",
        ],
    },
    "第二章_智能体发展史-answerable-002": {
        "question": "早期基于符号与逻辑的智能体有什么特点？",
        "expected_answer_points": [
            "以符号主义为核心",
            "通过规则操作符号来表示外部世界",
            "智能主要来自预先编码的知识库和推理规则",
        ],
    },
    "第二章_智能体发展史-answerable-003": {
        "question": "物理符号系统假说的核心论断是什么？",
        "expected_answer_points": [
            "物理符号系统具备产生通用智能的充分手段",
            "任何通用智能系统本质上都是物理符号系统",
            "智能的本质是符号的计算与处理",
        ],
    },
    "第二章_智能体发展史-rejectable-001": {
        "question": "文中是否列出了 ELIZA 项目的 GitHub 仓库地址和 release 版本号？",
    },
    "第五章_基于低代码平台的智能体搭建-answerable-001": {
        "question": "为什么这一章要讨论基于低代码平台的智能体搭建？",
        "expected_answer_points": [
            "纯代码开发并非总是最高效",
            "需要快速验证想法并降低构建门槛",
            "把重心从实现细节转向业务逻辑",
        ],
    },
    "第五章_基于低代码平台的智能体搭建-answerable-002": {
        "question": "平台化构建的兴起意味着什么？",
        "expected_answer_points": [
            "智能体构建正在走向平台化",
            "低代码平台支持图形化和模块化搭建",
            "开发重点转向快速调试和部署应用",
        ],
    },
    "第五章_基于低代码平台的智能体搭建-answerable-003": {
        "question": "为什么需要低代码平台？",
        "expected_answer_points": [
            "提升工程效率",
            "降低非专业开发者的参与门槛",
            "帮助快速验证想法和业务流程",
        ],
    },
    "第五章_基于低代码平台的智能体搭建-rejectable-001": {
        "question": "文中是否提供了 Coze 平台企业版的具体收费价格？",
    },
    "第八章_记忆与检索-answerable-001": {
        "question": "第八章主要围绕记忆与检索解决什么问题？",
        "expected_answer_points": [
            "将认知科学中的记忆机制引入智能体",
            "解释为什么需要记忆与 RAG",
            "设计记忆与检索系统架构",
        ],
    },
    "第八章_记忆与检索-answerable-002": {
        "question": "人类记忆系统给智能体带来哪些启发？",
        "expected_answer_points": [
            "记忆不是单一模块而是多系统协作",
            "短时记忆与长时记忆存在分工",
            "智能体也需要分层管理不同类型的信息",
        ],
    },
    "第八章_记忆与检索-answerable-003": {
        "question": "为什么智能体需要记忆与 RAG？",
        "expected_answer_points": [
            "仅靠上下文窗口难以处理跨轮信息",
            "需要长期保留用户与任务相关知识",
            "通过检索增强生成提升回答的相关性和准确性",
        ],
    },
    "第八章_记忆与检索-rejectable-001": {
        "question": "文中是否给出了向量数据库服务的商业采购报价？",
    },
    "第六章_框架开发实践-answerable-001": {
        "question": "第六章为什么从手动实现转向框架开发实践？",
        "expected_answer_points": [
            "从零实现有助于理解原理",
            "复杂应用需要更系统的框架支持",
            "开始比较和实践主流智能体框架",
        ],
    },
    "第六章_框架开发实践-answerable-002": {
        "question": "从手动实现到框架开发意味着什么转变？",
        "expected_answer_points": [
            "从单个案例实现转向工程化复用",
            "开始关注通用组件与开发效率",
            "为后续复杂应用构建统一基础",
        ],
    },
    "第六章_框架开发实践-answerable-003": {
        "question": "为什么需要智能体框架？",
        "expected_answer_points": [
            "统一组织模型、工具和记忆等能力",
            "减少重复开发",
            "提升扩展性与工程可维护性",
        ],
    },
    "第六章_框架开发实践-rejectable-001": {
        "question": "文中是否提供了 AutoGen 官方托管云服务的价格表？",
    },
    "第十一章_Agentic-RL-answerable-001": {
        "question": "Agentic RL 这一节要解决什么核心问题？",
        "expected_answer_points": [
            "提升智能体推理能力",
            "让智能体更好地使用工具",
            "让智能体具备自我改进能力",
        ],
    },
    "第十一章_Agentic-RL-answerable-002": {
        "question": "从强化学习到 Agentic RL 的映射关系是什么？",
        "expected_answer_points": [
            "把 LLM 智能体视为强化学习中的智能体",
            "环境由任务和验证系统构成",
            "状态包含问题描述和已有推理步骤",
            "行动是生成下一步推理或最终答案",
        ],
    },
    "第十一章_Agentic-RL-answerable-003": {
        "question": "LLM 训练全景图包含哪些主要阶段？",
        "expected_answer_points": [
            "预训练",
            "后训练",
            "从语言模型演化为对话助手",
        ],
    },
    "第十一章_Agentic-RL-rejectable-001": {
        "question": "文中是否给出了 Agentic RL 训练所需的具体显卡型号和费用预算？",
    },
    "第十三章_智能旅行助手-answerable-001": {
        "question": "智能旅行助手这一章的项目定位是什么？",
        "expected_answer_points": [
            "构建智能旅行助手项目",
            "围绕项目概述与架构设计展开",
            "通过案例展示智能体应用落地",
        ],
    },
    "第十三章_智能旅行助手-answerable-002": {
        "question": "为什么需要智能旅行助手？",
        "expected_answer_points": [
            "旅行规划信息繁杂且变化快",
            "用户需要综合行程、预算和偏好建议",
            "智能体可以提升规划效率与体验",
        ],
    },
    "第十三章_智能旅行助手-answerable-003": {
        "question": "智能旅行助手的技术架构包含哪些主要层次？",
        "expected_answer_points": [
            "前端交互层",
            "后端服务层",
            "智能体与工具集成层",
            "数据或外部服务层",
        ],
    },
    "第十三章_智能旅行助手-rejectable-001": {
        "question": "文中是否写明了旅行数据供应商 API 的商业合同价格？",
    },
    "第十二章_智能体性能评估-answerable-001": {
        "question": "第十二章主要介绍哪些评估相关内容？",
        "expected_answer_points": [
            "智能体评估基础",
            "为什么需要进行智能体评估",
            "如何通过示例开展性能评测",
        ],
    },
    "第十二章_智能体性能评估-answerable-002": {
        "question": "为什么需要智能体评估？",
        "expected_answer_points": [
            "不能只凭主观印象判断系统好坏",
            "需要量化比较不同模型和策略",
            "评估能指导系统优化与迭代",
        ],
    },
    "第十二章_智能体性能评估-answerable-003": {
        "question": "在评估示例开始时需要先做哪些初始化工作？",
        "expected_answer_points": [
            "创建 LLM",
            "创建智能体",
            "为后续评测准备运行对象",
        ],
    },
    "第十二章_智能体性能评估-rejectable-001": {
        "question": "本章是否给出了评测平台的 SaaS 订阅价格？",
    },
    "第十五章_构建赛博小镇-answerable-001": {
        "question": "构建赛博小镇这一章的项目目标是什么？",
        "expected_answer_points": [
            "构建 AI 小镇项目",
            "展示多智能体协作场景",
            "围绕项目概述与架构设计展开",
        ],
    },
    "第十五章_构建赛博小镇-answerable-002": {
        "question": "为什么要构建 AI 小镇？",
        "expected_answer_points": [
            "用多智能体模拟复杂社会协作",
            "验证智能体在开放环境中的行为",
            "展示从单体到群体智能的扩展",
        ],
    },
    "第十五章_构建赛博小镇-answerable-003": {
        "question": "AI 小镇的技术架构包含哪些主要层次？",
        "expected_answer_points": [
            "前端展示层",
            "后端服务层",
            "多智能体运行层",
            "数据与存储层",
        ],
    },
    "第十五章_构建赛博小镇-rejectable-001": {
        "question": "文中是否提供了 AI 小镇项目的正式部署域名？",
    },
    "第十六章_毕业设计-answerable-001": {
        "question": "第十六章的毕业设计部分希望完成什么目标？",
        "expected_answer_points": [
            "构建属于自己的多智能体应用",
            "把前面章节知识综合落地",
            "围绕选题、实现与展示展开",
        ],
    },
    "第十六章_毕业设计-answerable-002": {
        "question": "为什么要做毕业设计？",
        "expected_answer_points": [
            "通过完整项目巩固所学",
            "训练从问题定义到落地的能力",
            "形成可展示的作品与成果",
        ],
    },
    "第十六章_毕业设计-answerable-003": {
        "question": "毕业设计可以有哪些形式？",
        "expected_answer_points": [
            "从零构建原创项目",
            "对现有系统做深入扩展",
            "围绕多智能体场景完成综合应用",
        ],
    },
    "第十六章_毕业设计-rejectable-001": {
        "question": "文中是否指定了毕业设计必须提交的统一学校模板下载链接？",
    },
    "第十四章_自动化深度研究智能体-answerable-001": {
        "question": "自动化深度研究智能体这一章的核心目标是什么？",
        "expected_answer_points": [
            "构建自动化深度研究助手",
            "解决信息发散和事实更新快的问题",
            "交付带引用的可信研究报告",
        ],
    },
    "第十四章_自动化深度研究智能体-answerable-002": {
        "question": "为什么需要深度研究助手？",
        "expected_answer_points": [
            "信息过载",
            "缺少结构化整理",
            "重复进行搜索、阅读、总结的劳动",
        ],
    },
    "第十四章_自动化深度研究智能体-answerable-003": {
        "question": "深度研究助手的技术架构包含哪些主要层次？",
        "expected_answer_points": [
            "前端层",
            "后端层",
            "智能体层",
            "数据与工具层",
        ],
    },
    "第十四章_自动化深度研究智能体-rejectable-001": {
        "question": "文中是否给出了深度研究助手的生产环境域名和商业报价？",
    },
    "第十章_智能体通信协议-answerable-001": {
        "question": "第十章会引入哪些通信协议？",
        "expected_answer_points": [
            "MCP 用于智能体与工具的标准化通信",
            "A2A 用于智能体间点对点协作",
            "ANP 用于构建大规模智能体网络",
        ],
    },
    "第十章_智能体通信协议-answerable-002": {
        "question": "为什么需要通信协议？",
        "expected_answer_points": [
            "让智能体与外部世界高效交互",
            "支持多个智能体协作",
            "摆脱手工集成每个服务的方式",
        ],
    },
    "第十章_智能体通信协议-answerable-003": {
        "question": "单体智能体独立完成任务时有哪些根本限制？",
        "expected_answer_points": [
            "工具集成困难",
            "能力扩展受限",
            "缺少多智能体协作",
        ],
    },
    "第十章_智能体通信协议-rejectable-001": {
        "question": "文中是否规定了 A2A 协议的默认网络端口号？",
    },
    "第四章_智能体经典范式构建-answerable-001": {
        "question": "第四章将实现哪些经典智能体范式？",
        "expected_answer_points": [
            "ReAct",
            "Plan-and-Solve",
            "Reflection",
            "从零实现经典工作流",
        ],
    },
    "第四章_智能体经典范式构建-answerable-002": {
        "question": "开始构建前为什么要先做环境准备与基础工具定义？",
        "expected_answer_points": [
            "避免后续重复劳动",
            "先搭建开发环境",
            "先定义通用基础组件",
        ],
    },
    "第四章_智能体经典范式构建-answerable-003": {
        "question": "安装依赖库时至少需要准备哪些条件和库？",
        "expected_answer_points": [
            "Python 3.10 或更高版本",
            "openai 库",
            "python-dotenv 库",
        ],
    },
    "第四章_智能体经典范式构建-rejectable-001": {
        "question": "文中是否给出了 OpenAI API 的官方套餐价格表？",
    },
}


def load_records(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def apply_annotation_overrides(
    records: list[dict[str, Any]],
    overrides: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    updated_records: list[dict[str, Any]] = []

    for record in records:
        override = overrides.get(record["id"])
        if override is None:
            raise ValueError(f"Missing annotation override for record: {record['id']}")

        updated = dict(record)
        updated["question"] = override["question"]
        if not updated.get("allow_no_answer", False):
            updated["expected_answer_points"] = list(override.get("expected_answer_points", []))
        updated_records.append(updated)

    return updated_records


def validate_completed_annotations(records: list[dict[str, Any]]) -> None:
    for record in records:
        if not str(record.get("question", "")).strip():
            raise ValueError(f"Question is empty: {record['id']}")
        if not record.get("allow_no_answer", False) and not record.get("expected_answer_points"):
            raise ValueError(f"Answer points are empty for answerable record: {record['id']}")


def fill_seed_annotations(input_path: Path, output_path: Path | None = None) -> Path:
    records = load_records(input_path)
    updated_records = apply_annotation_overrides(records, ANNOTATION_OVERRIDES)
    validate_completed_annotations(updated_records)

    output_path = output_path or input_path
    write_records(output_path, updated_records)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill local DocQA seed annotations with grounded QA prompts.")
    parser.add_argument("--input", default=str(DEFAULT_SEED_PATH))
    parser.add_argument("--output", help="Optional output path. Defaults to overwriting the input file.")
    args = parser.parse_args()

    output_path = fill_seed_annotations(Path(args.input), Path(args.output) if args.output else None)
    print(json.dumps({"output_path": str(output_path), "records": len(ANNOTATION_OVERRIDES)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
