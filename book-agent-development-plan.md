# 📖 AI Book-Writing Agent 开发计划书（v2.0）

---

## 一、项目总览

### 1.1 项目愿景

构建一个具备 GUI 界面的智能写书 Agent，能够根据用户指定的**体裁（Genre）、题材（Theme）、篇幅（Scale）**自动生成结构完整、内容连贯、文学性达标的书籍。系统采用**模块化插件架构**，首期实现小说体裁下的推理、科幻、玄幻三种题材，其余体裁和题材预留标准化接口。

### 1.2 核心设计原则

- **可插拔体裁引擎**：每种体裁（小说/教科书/散文集等）是一个独立引擎，通过统一接口注册。
- **可插拔题材策略**：每种题材（推理/科幻/玄幻等）是引擎内的策略模块，决定核心要素与生成逻辑。
- **篇幅自适应**：从微型到超长篇，自动调整结构复杂度、人物数量、情节线数量。
- **上下文连贯性优先**：通过多层记忆系统保证前后文一致、伏笔回收、人设不崩。
- **可中断可恢复**：长篇/超长篇任务支持断点快照，任意时刻中断后可精确恢复。

### 1.3 技术选型（建议）

| 层级 | 技术 | 理由 |
|------|------|------|
| GUI 前端 | React + TypeScript + Tailwind | 组件化、生态丰富、快速开发 |
| 后端服务 | Python (FastAPI) | AI 生态最完善、异步支持好 |
| LLM 调用 | Anthropic Claude API / OpenAI API | 可替换的 LLM Provider 抽象层 |
| 持久化 | SQLite（本地）/ PostgreSQL（部署） | 存储项目、章节、世界观等结构化数据 |
| 向量存储 | ChromaDB / FAISS | 上下文检索、角色记忆、情节回溯 |
| 导出 | python-docx / WeasyPrint | 输出 .docx / .pdf 成品 |

---

## 二、系统架构

### 2.1 整体架构图

```
┌──────────────────────────────────────────────────────────────────────┐
│                            GUI 界面层                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌───────────┐  │
│  │ 创建向导  │ │ 写作控制台│ │ 预览/编辑 │ │审校报告  │ │ 导出/发布  │  │
│  └──────────┘ └──────────┘ └──────────┘ └─────────┘ └───────────┘  │
├──────────────────────────────────────────────────────────────────────┤
│                         API 网关 / 控制器层                           │
├──────────────────────────────────────────────────────────────────────┤
│                      核心编排引擎 (Orchestrator)                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Pipeline Manager + Checkpoint Manager                         │  │
│  │  规划 → 构建世界观 → 设计人物 → 拟大纲 → 逐章生成                  │  │
│  │  → 章节检查 → 审校 → 修订 → 导出                                 │  │
│  └────────────────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────────┤
│                          体裁引擎层                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐               │
│  │ 小说引擎  │ │教科书引擎 │ │散文集引擎 │ │ ...预留   │               │
│  │(已实现)   │ │(接口预留) │ │(接口预留) │ │          │               │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘               │
├──────────────────────────────────────────────────────────────────────┤
│                         题材策略层                                    │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                     │
│  │ 推理  │ │ 科幻  │ │ 玄幻  │ │ 悬疑  │ │...预留│                     │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘                     │
├──────────────────────────────────────────────────────────────────────┤
│                       智能基础设施层                                   │
│  ┌─────────┐ ┌─────────┐ ┌─────────────┐ ┌────────┐ ┌───────────┐ │
│  │ 记忆系统 │ │LLM适配器│ │题材专属检查器 │ │质量评估 │ │断点快照管理│ │
│  └─────────┘ └─────────┘ └─────────────┘ └────────┘ └───────────┘ │
├──────────────────────────────────────────────────────────────────────┤
│                       数据持久化层                                    │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐          │
│  │ 关系数据库  │ │ 向量数据库  │ │ 文件系统   │ │ 快照存储   │          │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘          │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心数据模型

```
BookProject
├── meta: { title, genre, theme, target_length, language }
├── creation_params: CreationParams         # 创建参数（通用+题材专属）
├── world_setting: WorldSetting             # 世界观
├── characters: Character[]                 # 角色表
├── plot_structure: PlotStructure           # 情节结构
├── outline: ChapterOutline[]               # 章节大纲
├── chapters: Chapter[]                     # 已生成章节
├── foreshadowing_registry: Foreshadow[]    # 伏笔注册表
├── theme_tracking_tables: ThemeTracker     # 题材专属追踪表（动态生成）
├── consistency_log: ConsistencyEntry[]     # 一致性日志
├── checkpoints: Checkpoint[]               # 断点快照列表
└── revision_history: Revision[]            # 修订历史
```

### 2.3 后台任务队列

GUI 不直接同步等待长任务完成。MVP 采用**轻量本地任务队列**，由 Pipeline Manager 调度章节生成、审计、快照保存、全局扫描、恢复验证等任务；后续云端部署时再替换为分布式队列。

```python
@dataclass
class WritingJob:
    id: str
    project_id: str
    type: Literal[
        "generate_chapter",
        "audit_chapter",
        "revise_chapter",
        "save_checkpoint",
        "restore_checkpoint",
        "global_scan",
        "rebuild_index",
    ]
    status: Literal["queued", "running", "paused", "cancelled", "failed", "completed"]
    progress: float
    current_step: str
    idempotency_key: str
    retry_count: int = 0
    error: str | None = None
```

任务队列规则：

1. 所有 LLM 调用、审计补丁、快照写入都必须带 `idempotency_key`，支持安全重试。
2. 同一项目同一时间只允许一个写状态任务运行；只读扫描和预览可并行。
3. 用户可暂停、取消、重试任务；取消只停止后续步骤，已提交的状态变更通过事件日志追踪。
4. 全局扫描、向量索引重建、恢复验证默认后台运行，不阻塞 GUI 浏览和编辑。

---

## 三、体裁引擎接口设计

### 3.1 统一体裁接口 `IGenreEngine`

```python
class IGenreEngine(ABC):
    """体裁引擎统一接口"""
    
    @abstractmethod
    def get_genre_name(self) -> str: ...
    
    @abstractmethod
    def get_supported_themes(self) -> list[str]: ...
    
    @abstractmethod
    def get_scale_configs(self) -> dict[str, ScaleConfig]: ...
    
    @abstractmethod
    def get_universal_params(self) -> list[ParamDefinition]: ...
    
    @abstractmethod
    def build_world(self, params: WorldBuildingParams) -> WorldSetting: ...
    
    @abstractmethod
    def design_characters(self, world: WorldSetting, params) -> list[Character]: ...
    
    @abstractmethod
    def generate_outline(self, world, characters, params) -> list[ChapterOutline]: ...
    
    @abstractmethod
    def write_chapter(self, chapter_outline, context: WritingContext) -> Chapter: ...
    
    @abstractmethod
    def review_and_revise(self, chapter: Chapter, context) -> Chapter: ...
    
    @abstractmethod
    def get_theme_strategy(self, theme_name: str) -> IThemeStrategy: ...
```

### 3.2 统一题材策略接口 `IThemeStrategy`

```python
class IThemeStrategy(ABC):
    """题材策略接口 — 定义某题材的核心要素和生成规则"""
    
    @abstractmethod
    def get_core_elements(self) -> list[CoreElement]: ...
    
    @abstractmethod
    def get_theme_specific_params(self) -> list[ThemeParam]: ...
    
    @abstractmethod
    def generate_param_options(self, param: ThemeParam, context) -> list[Option]: ...
    
    @abstractmethod
    def get_world_building_prompts(self) -> list[str]: ...
    
    @abstractmethod
    def get_character_archetypes(self) -> list[CharacterArchetype]: ...
    
    @abstractmethod
    def get_plot_patterns(self) -> list[PlotPattern]: ...
    
    @abstractmethod
    def get_quality_checklist(self) -> list[QualityRule]: ...
    
    @abstractmethod
    def customize_writing_style(self) -> StyleGuide: ...
    
    @abstractmethod
    def build_chapter_audit_prompt(self, chapter, audit_context: AuditPromptContext) -> str: ...
    
    @abstractmethod
    def get_tracking_table_schema(self) -> list[TrackingTableDef]: ...
    
    @abstractmethod
    def update_tracking_tables(self, tables, chapter, audit_result) -> dict: ...
```

### 3.3 预留体裁清单

| 体裁 | 状态 | 说明 |
|------|------|------|
| 小说 (Fiction) | ✅ 首期实现 | 含推理/科幻/玄幻三种题材 |
| 教科书 (Textbook) | 🔲 接口预留 | 知识体系构建、习题生成、难度递进 |
| 散文集 (Essay) | 🔲 接口预留 | 主题散文、游记、杂文 |
| 诗集 (Poetry) | 🔲 接口预留 | 格律诗、自由诗、组诗 |
| 剧本 (Screenplay) | 🔲 接口预留 | 影视/话剧/舞台剧 |
| 非虚构 (Non-fiction) | 🔲 接口预留 | 传记、纪实文学 |

---

## 四、创建参数体系：通用参数 + LLM 生成 + 题材专属

创建向导的参数采用 **三层结构**：通用参数（所有体裁/题材共用）、LLM 辅助生成参数（系统提出建议由用户选择或修改）、题材专属参数（由题材策略定义，支持 LLM 生成候选项或用户自定义）。

### 4.1 通用参数（用户填写）

所有书籍项目都需要的基础信息，由用户直接填写：

```python
UNIVERSAL_PARAMS = [
    ParamDefinition(
        key="title",
        label="书名",
        type="text",
        required=False,           # 可留空让 LLM 在完成世界观后建议
        hint="留空可稍后由 AI 建议",
    ),
    ParamDefinition(
        key="core_idea",
        label="核心创意 / 一句话概括",
        type="textarea",
        required=True,
        hint="例：一个密室杀人案，凶手其实是叙述者自己",
        max_length=500,
    ),
    ParamDefinition(
        key="target_audience",
        label="目标读者",
        type="single_select",
        options=["少年(12-17)", "青年(18-30)", "成人(30+)", "全年龄"],
        default="青年(18-30)",
    ),
    ParamDefinition(
        key="language_style",
        label="语言风格倾向",
        type="single_select",
        options=["文学性/典雅", "通俗流畅", "网文/口语化", "硬核/学术感"],
        default="通俗流畅",
    ),
    ParamDefinition(
        key="narrative_pov",
        label="叙事视角",
        type="single_select",
        options=["第一人称", "第三人称有限", "第三人称全知", "多视角轮换"],
        default="第三人称有限",
    ),
    ParamDefinition(
        key="tone",
        label="整体基调",
        type="multi_select",
        options=["严肃", "轻松", "黑暗", "温暖", "幽默", "史诗感", "荒诞"],
    ),
    ParamDefinition(
        key="special_requirements",
        label="特殊要求（自由文本）",
        type="textarea",
        required=False,
        hint="任何额外的写作要求、禁忌、偏好等",
    ),
]
```

### 4.2 LLM 辅助生成参数（系统建议 + 用户选择）

用户填完通用参数后，系统调用 LLM 根据已有信息生成建议，用户可选择采用或修改：

```python
LLM_SUGGESTED_PARAMS = [
    SuggestedParam(
        key="title_suggestions",
        label="书名建议",
        trigger="当用户未填写 title 时",
        generation_prompt="根据以下核心创意和题材，生成5个书名候选...",
        ui_type="radio_or_custom",       # 可选建议项或自定义输入
        count=5,
    ),
    SuggestedParam(
        key="era_setting",
        label="时代背景建议",
        trigger="始终生成",
        generation_prompt="根据核心创意，建议3种合适的时代背景设定...",
        ui_type="radio_or_custom",
        count=3,
    ),
    SuggestedParam(
        key="ending_tendency",
        label="结局走向",
        trigger="始终生成",
        generation_prompt="根据题材和基调，建议3种可能的结局走向...",
        ui_type="radio_or_custom",
        count=3,
    ),
    SuggestedParam(
        key="emotional_arc",
        label="情感曲线建议",
        trigger="中篇及以上",
        generation_prompt="设计3种不同的全书情感曲线（如低开高走/过山车/...）",
        ui_type="radio_or_custom",
        count=3,
    ),
]
```

### 4.3 题材专属参数（由 ThemeStrategy 定义）

每种题材有独特的核心参数，同样支持 **LLM 生成候选** 和 **用户自定义** 两种模式：

#### 4.3.1 推理小说专属参数

```python
class MysteryThemeParams:
    params = [
        ThemeParam(
            key="core_trick",
            label="核心诡计",
            type="llm_generate_or_custom",    # 关键：LLM生成 或 自定义
            generation_prompt="""
                根据以下核心创意，设计5种不同类型的核心诡计方案，
                每种方案包含：诡计类型（密室/不在场证明/叙述性/心理/机械）、
                诡计简述（50字以内）、可行性评级（高/中/低）、
                新颖度评级（常见/较新/创新）。
            """,
            count=5,
            allow_custom=True,
            custom_hint="描述你想要的核心诡计，包括类型和大致手法",
        ),
        ThemeParam(
            key="mystery_subgenre",
            label="推理子类型",
            type="single_select",
            options=["本格推理", "社会派推理", "日常之谜", "倒叙推理", "法庭推理"],
        ),
        ThemeParam(
            key="detective_type",
            label="侦探类型",
            type="llm_generate_or_custom",
            generation_prompt="设计4种风格各异的侦探人设，含性格特点、推理风格、标志性习惯...",
            count=4,
            allow_custom=True,
        ),
        ThemeParam(
            key="victim_count",
            label="受害者数量",
            type="number_range",
            min=1, max=10, default=1,
            hint="连环案件可设置多个受害者",
        ),
        ThemeParam(
            key="clue_density",
            label="线索密度",
            type="single_select",
            options=["密集（挑战读者型）", "适中（经典推理型）", "稀疏（氛围悬疑型）"],
            default="适中（经典推理型）",
        ),
        ThemeParam(
            key="red_herring_count",
            label="误导线索数量",
            type="llm_generate_or_custom",
            generation_prompt="根据案件规模和篇幅，建议3种误导线索配置方案...",
            count=3,
            allow_custom=True,
        ),
        ThemeParam(
            key="fairness_level",
            label="公平性等级",
            type="single_select",
            options=[
                "严格公平（所有线索明确呈现，读者可推理出真相）",
                "基本公平（关键线索呈现，部分需要洞察力）",
                "氛围优先（重悬疑感，不强求读者可独立推理）",
            ],
            default="基本公平（关键线索呈现，部分需要洞察力）",
        ),
    ]
```

#### 4.3.2 科幻小说专属参数

```python
class SciFiThemeParams:
    params = [
        ThemeParam(
            key="sci_fi_subgenre",
            label="科幻子类型",
            type="single_select",
            options=["太空歌剧", "赛博朋克", "末日/后末日", "时间旅行",
                     "第一接触", "近未来", "生物朋克", "蒸汽朋克"],
        ),
        ThemeParam(
            key="hardness",
            label="科幻硬度",
            type="single_select",
            options=[
                "硬科幻（严格遵循已知科学原理）",
                "中等（有科学基础但允许合理外推）",
                "软科幻（科技为背景，重点在人文/社会）",
            ],
            default="中等（有科学基础但允许合理外推）",
        ),
        ThemeParam(
            key="core_technology",
            label="核心科技设定",
            type="llm_generate_or_custom",
            generation_prompt="""
                根据核心创意和子类型，设计5种核心科技设定方案，
                每种包含：技术名称、科学原理基础、对社会的影响、
                技术限制/代价、创新度评级。
            """,
            count=5,
            allow_custom=True,
            custom_hint="描述你想要的核心科技，包括原理和限制",
        ),
        ThemeParam(
            key="time_setting",
            label="时间设定",
            type="llm_generate_or_custom",
            generation_prompt="根据子类型，建议3个合适的时间设定及对应的文明发展程度...",
            count=3,
            allow_custom=True,
        ),
        ThemeParam(
            key="alien_presence",
            label="外星文明",
            type="single_select",
            options=["无外星文明", "有但未接触", "已接触/共存", "外星为核心冲突"],
            default="无外星文明",
        ),
        ThemeParam(
            key="philosophical_core",
            label="哲学内核",
            type="llm_generate_or_custom",
            generation_prompt="根据核心创意，建议4个值得探讨的哲学/伦理主题...",
            count=4,
            allow_custom=True,
        ),
    ]
```

#### 4.3.3 玄幻小说专属参数

```python
class XuanhuanThemeParams:
    params = [
        ThemeParam(
            key="power_system",
            label="修炼/力量体系",
            type="llm_generate_or_custom",
            generation_prompt="""
                设计4套不同风格的修炼体系，每套包含：
                体系名称、等级划分（6-12级）、修炼资源、
                突破机制、体系特色、与常见体系的差异化亮点。
            """,
            count=4,
            allow_custom=True,
            custom_hint="描述你想要的修炼体系，包括等级划分和特色",
        ),
        ThemeParam(
            key="golden_finger",
            label="主角金手指/外挂",
            type="llm_generate_or_custom",
            generation_prompt="""
                根据核心创意和修炼体系，设计5种金手指方案，
                每种包含：名称、能力描述、成长性、代价/限制、
                与主线的关联方式。
            """,
            count=5,
            allow_custom=True,
        ),
        ThemeParam(
            key="world_scale",
            label="世界规模",
            type="single_select",
            options=["单一大陆", "多大陆/海域", "多位面/界域", "星域/宇宙级"],
            default="单一大陆",
        ),
        ThemeParam(
            key="shuang_dian_style",
            label="爽点风格倾向",
            type="multi_select",
            options=["打脸装逼", "实力碾压", "奇遇连连", "势力建设",
                     "炼丹/炼器", "拍卖竞价", "大比争锋", "秘境探索"],
        ),
        ThemeParam(
            key="conflict_escalation_path",
            label="冲突升级路线",
            type="llm_generate_or_custom",
            generation_prompt="根据世界规模和篇幅，设计3条冲突升级路线...",
            count=3,
            allow_custom=True,
        ),
        ThemeParam(
            key="mc_starting_point",
            label="主角起点",
            type="single_select",
            options=["废柴/低谷", "天才陨落", "穿越重生", "普通人奇遇", "隐藏血脉"],
            default="废柴/低谷",
        ),
    ]
```

### 4.4 参数填写的 GUI 交互流程

```
步骤 1: 选择体裁 + 题材 + 篇幅
    │
    ▼
步骤 2: 通用参数表单
    │  用户填写：核心创意、目标读者、语言风格、叙事视角、基调...
    │
    ▼
步骤 3: LLM 辅助建议（异步生成，约 5-10 秒）
    │  系统根据步骤2的输入，调用 LLM 生成建议项
    │  ┌──────────────────────────────────────────────┐
    │  │ 📝 书名建议:                                  │
    │  │   ○ 《镜中之罪》                              │
    │  │   ○ 《第七个证人》                             │
    │  │   ○ 《消失的三小时》                           │
    │  │   ○ 自定义: [________________]               │
    │  │                                              │
    │  │ 🕐 时代背景:                                   │
    │  │   ○ 现代都市（2020年代某一线城市）              │
    │  │   ○ 民国时期上海租界                           │
    │  │   ○ 近未来（2040年代，AI普及社会）              │
    │  │   ○ 自定义: [________________]               │
    │  └──────────────────────────────────────────────┘
    │
    ▼
步骤 4: 题材专属参数表单
    │  根据所选题材，动态加载专属参数
    │  每个 llm_generate_or_custom 类型的参数：
    │  ┌──────────────────────────────────────────────┐
    │  │ 🔍 核心诡计:                                   │
    │  │   [🤖 AI生成方案]  [✏️ 自定义输入]    ← 模式切换 │
    │  │                                              │
    │  │   AI生成模式:                                  │
    │  │   ○ 密室诡计：利用气压差和窗户的自锁装置...     │
    │  │     可行性:高 | 新颖度:较新                     │
    │  │   ○ 不在场证明：利用预录视频和定时装置...       │
    │  │     可行性:高 | 新颖度:常见                     │
    │  │   ○ 叙述性诡计：第一人称叙述者隐瞒了...        │
    │  │     可行性:中 | 新颖度:创新                     │
    │  │   ○ [🔄 重新生成]                              │
    │  │                                              │
    │  │   自定义模式:                                  │
    │  │   [多行文本输入框______________________]       │
    │  │   描述你想要的核心诡计...                       │
    │  └──────────────────────────────────────────────┘
    │
    ▼
步骤 5: 参数确认总览
    │  展示所有已填参数的摘要，允许回退修改任意步骤
    │
    ▼
开始生成 →→→ 进入世界观构建阶段
```

### 4.5 参数选项的再生成机制

```python
class ParamOptionGenerator:
    """参数选项生成器 — 支持首次生成、重新生成、基于反馈优化"""
    
    async def generate_options(self, param: ThemeParam, context: dict) -> list[Option]:
        """首次生成：根据已有上下文生成候选项"""
        prompt = param.generation_prompt.format(**context)
        return await self.llm.generate_structured(prompt, count=param.count)
    
    async def regenerate_options(self, param: ThemeParam, context: dict, 
                                  feedback: str = None) -> list[Option]:
        """重新生成：可附带用户反馈以获得更贴近需求的选项"""
        if feedback:
            prompt = f"之前的方案用户不满意，反馈是：{feedback}。请重新设计..."
        else:
            prompt = f"请生成与上一批完全不同的方案..."
        return await self.llm.generate_structured(prompt, count=param.count)
    
    async def refine_custom_input(self, param: ThemeParam, 
                                   user_input: str, context: dict) -> Option:
        """优化自定义输入：帮用户补全细节、检查可行性"""
        prompt = f"用户自定义了以下方案：{user_input}，请帮助补全细节和评估可行性..."
        return await self.llm.generate_structured(prompt, count=1)
```

---

## 五、小说引擎详细设计

### 5.1 篇幅分级与参数配置

字数与章节区间是推荐档位；边界值由创建向导按更高篇幅归类，确保不会出现 50-100 万字空档。

```python
SCALE_CONFIGS = {
    "micro": ScaleConfig(
        name="微型小说",
        word_range=(300, 1500),
        chapter_count=1,
        character_limit=3,
        plot_lines=1,
        structure="单一场景/单一反转",
        foreshadow_depth=0,
        context_window="full",
        generation_strategy="single_pass",
        checkpoint_strategy="none",          # 无需断点
    ),
    "short": ScaleConfig(
        name="短篇小说",
        word_range=(3000, 30000),
        chapter_count=(1, 8),
        character_limit=8,
        plot_lines=1,
        structure="三幕式/起承转合",
        foreshadow_depth=1,
        context_window="full",
        generation_strategy="sequential",
        checkpoint_strategy="per_chapter",   # 每章保存
    ),
    "medium": ScaleConfig(
        name="中篇小说",
        word_range=(30000, 100000),
        chapter_count=(10, 30),
        character_limit=20,
        plot_lines=(2, 3),
        structure="多线交织/三幕+副线",
        foreshadow_depth=2,
        context_window="sliding_window",
        generation_strategy="chapter_by_chapter",
        checkpoint_strategy="per_chapter",
    ),
    "long": ScaleConfig(
        name="长篇小说",
        word_range=(100000, 999999),
        chapter_count=(30, 299),
        character_limit=50,
        plot_lines=(3, 6),
        structure="多卷/多线/多视角",
        foreshadow_depth=3,
        context_window="hierarchical_memory",
        generation_strategy="arc_based",
        checkpoint_strategy="per_chapter_with_full_snapshot",
    ),
    "epic": ScaleConfig(
        name="超长篇小说",
        word_range=(1000000, None),
        chapter_count=(300, None),
        character_limit=None,
        plot_lines=(5, None),
        structure="多部曲/编年体/世界编年史",
        foreshadow_depth=4,
        context_window="hierarchical_memory + vector_retrieval",
        generation_strategy="volume_based",
        checkpoint_strategy="per_chapter_with_full_snapshot",
    ),
}
```

### 5.2 推理小说题材策略

```python
class MysteryThemeStrategy(IThemeStrategy):
    """推理小说策略 — 逻辑为王，公平性是底线"""
    
    core_elements = [
        CoreElement("crime_design", "案件设计", priority=1,
            sub_elements=[
                "犯罪手法 (Trick/Method)",
                "犯罪动机 (Motive)",
                "作案时间线 (Timeline)",
                "物证/人证链 (Evidence Chain)",
            ]),
        CoreElement("trick_system", "诡计体系", priority=1,
            sub_elements=[
                "密室诡计 (Locked Room)",
                "不在场证明 (Alibi Trick)",
                "叙述性诡计 (Narrative Trick)",
                "心理诡计 (Psychological Trick)",
                "机械诡计 (Mechanical Trick)",
            ]),
        CoreElement("investigation", "调查推理", priority=1,
            sub_elements=[
                "线索搜集与解读",
                "嫌疑人排查",
                "逻辑推演链",
                "误导线索 (Red Herring)",
            ]),
        CoreElement("fairness", "公平性原则", priority=1,
            description="诺克斯十诫/范达因二十则的现代化适用"),
        CoreElement("reveal", "揭示与解答", priority=2,
            sub_elements=[
                "挑战读者 (Challenge to Reader)",
                "解答篇结构",
                "逻辑闭环验证",
            ]),
    ]
    
    character_archetypes = [
        "侦探/推理者 (Detective)",
        "助手/叙述者 (Watson)",
        "凶手 (Culprit)",
        "受害者 (Victim)",
        "嫌疑人群 (Suspects)",
        "目击者 (Witness)",
    ]
    
    plot_patterns = [
        "本格推理: 案件→调查→推理→解答",
        "社会派推理: 动机探究→社会背景→真相",
        "日常之谜: 小事件→巧妙解答",
        "倒叙推理: 已知凶手→破解手法",
    ]
```

### 5.3 科幻小说题材策略

```python
class SciFiThemeStrategy(IThemeStrategy):
    """科幻小说策略 — 科学外推 + 思想实验"""
    
    core_elements = [
        CoreElement("science_core", "科学内核", priority=1,
            sub_elements=[
                "核心科技设定 (Core Tech Premise)",
                "科学原理依据 (Scientific Basis)",
                "技术推演链 (Tech Extrapolation)",
                "硬度等级 (Hardness Scale: 硬/中/软)",
            ]),
        CoreElement("world_future", "未来世界构建", priority=1,
            sub_elements=[
                "时间设定 (Time Setting)",
                "社会形态 (Social Structure)",
                "科技水平 (Tech Level)",
                "星际/行星/赛博等子类型环境",
            ]),
        CoreElement("thought_experiment", "思想实验", priority=2,
            sub_elements=[
                "科技对人性的影响",
                "文明发展悖论",
                "存在主义探讨",
                "伦理困境",
            ]),
        CoreElement("sense_of_wonder", "惊奇感 (Sense of Wonder)", priority=1,
            description="让读者体验到超越日常认知的震撼"),
        CoreElement("internal_consistency", "设定自洽", priority=1,
            description="科技设定在全文中保持一致，不自相矛盾"),
    ]
    
    character_archetypes = [
        "科学家/工程师 (Scientist)",
        "探索者/宇航员 (Explorer)",
        "AI/机器人 (Artificial Intelligence)",
        "异星种族 (Alien Species)",
        "反抗者 (Rebel against system)",
        "普通人视角 (Everyman POV)",
    ]
    
    plot_patterns = [
        "太空歌剧: 星际冲突→冒险→文明碰撞",
        "赛博朋克: 底层逆袭→揭露阴谋→拷问人性",
        "末日/后末日: 灾难→生存→重建",
        "第一接触: 发现→交流→理解/冲突",
        "时间旅行: 悖论→因果→解决",
    ]
```

### 5.4 玄幻小说题材策略

```python
class XuanhuanThemeStrategy(IThemeStrategy):
    """玄幻小说策略 — 世界观为骨，爽感为魂"""
    
    core_elements = [
        CoreElement("power_system", "力量体系", priority=1,
            sub_elements=[
                "修炼等级 (Cultivation Levels)",
                "功法/技能体系 (Skills/Techniques)",
                "天材地宝/资源体系 (Resources)",
                "战力量化与进阶逻辑",
                "境界突破机制 (Breakthrough Mechanics)",
            ]),
        CoreElement("world_cosmology", "世界观与宇宙观", priority=1,
            sub_elements=[
                "大陆/位面/界域划分",
                "种族/势力/宗门体系",
                "天道/规则体系",
                "上古历史与传说",
            ]),
        CoreElement("shuang_dian", "爽点设计", priority=1,
            sub_elements=[
                "打脸 (Face-slapping)",
                "逆袭 (Reversal/Underdog Rise)",
                "奇遇 (Serendipity/Lucky Encounters)",
                "装逼 (Showing Off/Power Display)",
                "碾压 (Overwhelming Power)",
                "节奏控制 (抑→扬 的情绪曲线)",
            ]),
        CoreElement("conflict_escalation", "冲突升级", priority=2,
            sub_elements=[
                "个人→家族→宗门→国家→大陆→位面→宇宙",
                "对手等级递增",
                "赌注递增",
            ]),
        CoreElement("golden_finger", "金手指/外挂", priority=2,
            description="主角独有的核心优势，需有代价或限制以保持张力"),
    ]
    
    character_archetypes = [
        "主角 (MC with Golden Finger)",
        "红颜知己/后宫 (Female Leads)",
        "兄弟/忠仆 (Loyal Companions)",
        "反派 (Escalating Villains)",
        "神秘老者/师父 (Mysterious Elder)",
        "天才少年/世家子弟 (Rival Genius)",
    ]
    
    plot_patterns = [
        "废柴逆袭: 被辱→奇遇→崛起→复仇→更大世界",
        "宗门争霸: 入门→争锋→大比→秘境→晋升",
        "大陆漫游: 历练→奇遇→势力建设→称霸",
        "位面穿越: 低级位面→渡劫→飞升→高级位面循环",
    ]
```

### 5.5 预留题材清单

| 题材 | 状态 | 核心要素（概要） |
|------|------|-----------------|
| 推理 | ✅ 已设计 | 诡计、线索、公平性、逻辑闭环 |
| 科幻 | ✅ 已设计 | 科学内核、惊奇感、设定自洽 |
| 玄幻 | ✅ 已设计 | 力量体系、爽点设计、世界观 |
| 悬疑 | 🔲 预留 | 悬念设置、氛围营造、真相反转 |
| 言情 | 🔲 预留 | 人物化学反应、情感弧线、甜虐节奏 |
| 历史 | 🔲 预留 | 史实考据、时代氛围、虚实结合 |
| 武侠 | 🔲 预留 | 江湖设定、武功体系、侠义精神 |
| 恐怖 | 🔲 预留 | 恐惧递进、氛围渲染、未知威胁 |
| 都市 | 🔲 预留 | 现实感、社会关系、职场/生活 |

---

## 六、核心难点：上下文连贯性系统

这是本项目最关键也最困难的部分。LLM 的上下文窗口有限，但一本长篇小说可能达几十万字。必须通过多层记忆架构来保障连贯性。

### 6.1 四层记忆架构

```
┌─────────────────────────────────────────────────┐
│  L0: 即时上下文 (Working Memory)                  │
│  当前章节 + 前一章节尾部 + 当前章节大纲              │
│  直接放入 LLM 上下文窗口                           │
├─────────────────────────────────────────────────┤
│  L1: 短期记忆 (Short-term Memory)                │
│  最近 3-5 章的摘要 + 关键事件 + 角色状态变化          │
│  压缩后放入上下文窗口                               │
├─────────────────────────────────────────────────┤
│  L2: 结构记忆 (Structural Memory)                │
│  全书大纲 + 人物关系图 + 世界观文档 + 时间线          │
│  + 伏笔注册表 + 已解决/未解决的悬念列表              │
│  + 题材专属追踪表                                  │
│  按需检索，以摘要形式注入上下文                      │
├─────────────────────────────────────────────────┤
│  L3: 长期记忆 (Long-term Memory / Vector Store)  │
│  所有已生成章节的向量索引                           │
│  按语义相关性检索，当需要引用/呼应远处情节时使用       │
└─────────────────────────────────────────────────┘
```

### 6.2 伏笔管理系统

```python
@dataclass
class Foreshadow:
    id: str
    type: str                  # "线索" | "暗示" | "预言" | "物件" | "角色背景"
    description: str           # 伏笔内容描述
    planted_chapter: int       # 埋设章节
    planted_text: str          # 原文片段
    intended_payoff: str       # 计划的回收方式
    payoff_chapter: int | None # 计划回收章节
    status: str                # "planted" | "reinforced" | "resolved" | "abandoned"
    urgency: int               # 1-5, 越高越需尽快回收
    reinforcements: list[dict] # 中间强化/暗示记录
    resolution: dict | None    # 实际回收记录
    cross_volume: bool         # 是否跨卷伏笔（长篇/超长篇）
    related_foreshadows: list[str]  # 关联伏笔 ID 列表
```

伏笔生命周期：**埋设→强化→回收→审计**，与 v1 相同，但增加跨卷关联和关联伏笔链功能。

### 6.3 不同篇幅下的上下文策略

| 篇幅 | 上下文策略 | 伏笔深度 | 一致性检查频率 |
|------|-----------|---------|--------------|
| 微型 | 全文在单次上下文内 | 无 | 生成后一次 |
| 短篇 | 全文在上下文内 | 简单（1-2 个） | 每章一次 |
| 中篇 | L0+L1+L2 摘要 | 中等（5-10 个） | 每章一次 + 每幕一次全局检查 |
| 长篇 | 四层全用 | 复杂（20+ 个） | 每章 + 每卷全局 + 向量检索辅助 |
| 超长篇 | 四层 + 分卷独立记忆 + 跨卷向量索引 | 极复杂 | 每章 + 每弧 + 每卷 + 定期全局审计 |

---

## 七、题材专属章节审计系统

v1 版只有通用一致性检查。v2 引入**题材专属审计**：每章完成后，除通用检查外，系统根据题材自动生成**专属追踪表**，并逐项比对当前章节与全局状态的一致性。

### 7.1 审计架构

```
章节生成完成
    │
    ▼
[通用检查层] ──── 所有题材共用
    │  角色一致性、时间线、空间、情节逻辑（同v1）
    │
    ▼
[题材专属检查层] ──── 由 ThemeStrategy 动态生成
    │  调用 ThemeStrategy.build_chapter_audit_prompt()
    │  生成题材相关的检查项清单
    │  逐项审计并更新追踪表
    │
    ▼
[追踪表更新] ──── 题材专属状态表实时更新
    │  调用 ThemeStrategy.update_tracking_tables()
    │
    ▼
[综合审计报告] ──── 合并通用 + 专属结果
    通过: 进入下一章
    不通过: 标记问题 → 自动修订 或 人工干预
```

### 7.2 通用检查项（所有题材共用）

```python
class UniversalChapterAudit:
    """每章必检的通用项"""
    
    checks = {
        "character_consistency": {
            "label": "角色一致性",
            "items": [
                "本章出场角色是否都在角色表中（无凭空出现的新角色）",
                "角色外貌描写是否与角色表一致（发色/瞳色/体型/年龄/着装标志等）",
                "角色性格表现是否与设定吻合（内向角色不应突然变外向且无铺垫）",
                "角色之间的称呼是否前后统一（不会一章叫'师兄'下一章叫'老大'）",
                "已死亡/已离场角色是否意外出现",
                "角色持有物品是否与上章末尾一致（不会凭空出现/消失道具）",
                "角色已知信息边界是否正确（不应知道未被告知的事）",
            ],
        },
        "timeline_consistency": {
            "label": "时间线一致性",
            "items": [
                "事件发生时间是否与全局时间线吻合",
                "日/夜、季节、天气等描写是否自洽",
                "角色年龄变化是否合理",
                "上章结尾时间 → 本章开头时间的过渡是否合逻辑",
                "'三天前''上周'等相对时间表述是否与实际时间线吻合",
            ],
        },
        "spatial_consistency": {
            "label": "空间一致性",
            "items": [
                "地点名称是否与世界观文档一致",
                "角色位移距离与耗时是否合理",
                "场景内部布局描写是否与前文一致（门窗位置、家具摆放等）",
                "多角色同时在场时的空间位置关系是否合逻辑",
            ],
        },
        "plot_logic": {
            "label": "情节逻辑",
            "items": [
                "因果关系是否成立",
                "角色的行为动机是否可被理解",
                "前文已建立的规则/约定是否被遵守",
                "已解决的问题不应再被当作悬念",
                "前文重要对话/承诺是否被角色记住",
            ],
        },
        "narrative_quality": {
            "label": "叙事质量",
            "items": [
                "本章与上章的衔接是否自然流畅",
                "叙事视角是否保持一致（不应无故切换人称）",
                "信息密度是否适当（不过于冗长也不过于跳跃）",
                "对话风格是否符合各角色人设",
                "本章字数是否在预期范围内",
            ],
        },
    }
```

### 7.2.1 追踪表 Schema 与幂等补丁规范

上面的题材追踪表会展示业务列，但实际实现不能只依赖中文列名。每张表必须由 `TrackingTableDef` 提供稳定 ID、主键、唯一键和补丁合并策略，确保审计重跑、章节恢复、人工编辑回放时不会重复插入或覆盖错误状态。

```python
@dataclass
class TrackingColumnDef:
    key: str
    label: str
    type: Literal["string", "number", "enum", "chapter_ref", "entity_ref", "list", "object"]
    required: bool = False
    enum_values: list[str] | None = None


@dataclass
class TrackingTableDef:
    table_id: str                         # 稳定机器 ID，如 "mystery.clues"
    name: str                             # GUI 展示名，如 "线索追踪表"
    primary_key: str                      # 行主键，如 "clue_id"
    unique_keys: list[list[str]]          # 幂等判断，如 [["线索描述", "首次出现章节"]]
    columns: list[TrackingColumnDef]
    audit_rules: list[str]
    merge_policy: Literal["append_only", "upsert_by_pk", "manual_on_conflict"]


@dataclass
class AuditPromptContext:
    table_def: TrackingTableDef
    current_rows: list[dict]
    project_context: str
    required_output_schema: type
```

补丁应用规则：

1. `insert` 必须携带主键；若缺主键，则由表的 `unique_keys` 生成确定性主键。
2. `update` 必须携带 `base_row_version`，版本不一致时进入冲突处理，不直接覆盖。
3. 同一个 `idempotency_key` 的补丁重复提交时只能生效一次。
4. `append_only` 表不允许删除或覆盖历史记录，只能追加状态变更。
5. 人工确认的行优先级高于自动审计补丁，除非用户显式允许覆盖。

状态更新采用“LLM 输出补丁、程序应用补丁”的模式：LLM 只负责从章节和上下文中提取变更，输出 `TablePatch[]`；程序负责校验主键、版本、幂等、冲突策略和最终落库。禁止让 LLM 直接返回整张最终表覆盖当前状态。

### 7.3 推理小说专属审计

```python
class MysteryChapterAudit:
    """推理小说每章专属检查 — 围绕线索链和逻辑公平性"""
    
    # ═══════════════════════════════════════════════
    #  追踪表 1: 线索追踪表 (Clue Registry)
    # ═══════════════════════════════════════════════
    clue_tracking_table = {
        "name": "线索追踪表",
        "description": "记录所有已出现的真实线索和误导线索",
        "columns": [
            "线索ID", "线索描述", "首次出现章节", "出现方式（对话/叙述/物件/行为）",
            "发现者", "类型（真实/误导/待定）",
            "指向（指向真相的哪个部分 或 误导方向）",
            "当前状态（已呈现/已被侦探注意/已解读/已排除）",
            "解答章节", "与真相的关联说明",
        ],
        "audit_rules": [
            "新出现的线索是否已录入追踪表",
            "本章是否有对旧线索的回顾/重新解读",
            "线索出现的时机是否自然（不突兀、不刻意）",
            "到当前章节为止，读者理论上能获得的真实线索清单是否符合预期进度",
            "误导线索的误导方向是否有足够的说服力",
            "已排除的误导线索是否给出了合理的排除理由",
        ],
    }
    
    # ═══════════════════════════════════════════════
    #  追踪表 2: 嫌疑人状态表
    # ═══════════════════════════════════════════════
    suspect_tracking_table = {
        "name": "嫌疑人状态表",
        "columns": [
            "角色名", "嫌疑等级（高/中/低/已排除/真凶）",
            "动机", "不在场证明（有/无/存疑）",
            "与受害者关系", "可疑行为记录",
            "本章状态变化", "读者视角嫌疑排序",
        ],
        "audit_rules": [
            "嫌疑人的嫌疑等级变化是否有事件/线索支撑",
            "不在场证明的建立和破解是否合逻辑",
            "是否每隔几章就有嫌疑格局的变化（避免停滞）",
            "真凶在读者视角中的嫌疑等级是否符合剧情进度（不能太早暴露也不能完全隐身）",
            "已排除的嫌疑人排除理由是否充分",
        ],
    }
    
    # ═══════════════════════════════════════════════
    #  追踪表 3: 作案时间线对照表
    # ═══════════════════════════════════════════════
    crime_timeline_table = {
        "name": "作案时间线对照表",
        "columns": [
            "时间点", "真实事件（作者/系统视角）",
            "各角色位置和行动",
            "侦探已知信息", "读者已知信息",
            "信息差（侦探 vs 读者 vs 真相）",
        ],
        "audit_rules": [
            "本章新揭示的时间线信息是否与已建立的真实时间线吻合",
            "各角色在关键时间点的位置是否自洽",
            "侦探的已知信息是否只来源于其调查过程（不能凭空获知）",
            "信息差是否在按计划缩小",
        ],
    }
    
    # ═══════════════════════════════════════════════
    #  追踪表 4: 诡计完整性检查表
    # ═══════════════════════════════════════════════
    trick_integrity_table = {
        "name": "诡计完整性检查表",
        "columns": [
            "诡计要素", "是否已在正文中埋设对应线索",
            "线索所在章节", "线索呈现方式",
            "读者是否能从该线索推导出此要素",
        ],
        "audit_rules": [
            "核心诡计的每个构成要素是否都有对应线索在正文中出现",
            "到目前章节，公平性进度是否达标（解答前80%的必要线索应已呈现）",
            "诡计的物理/逻辑可行性是否在正文叙述中得到了间接支撑",
        ],
    }

    # ═══════════════════════════════════════════════
    #  追踪表 5: 推理逻辑链验证表
    # ═══════════════════════════════════════════════
    reasoning_chain_table = {
        "name": "推理逻辑链验证表",
        "columns": [
            "推理步骤编号", "前提（已知线索/事实）",
            "推理过程", "结论",
            "该推理是否已在正文中呈现", "所在章节",
        ],
        "audit_rules": [
            "侦探的每一步推理是否有充分的前提支撑",
            "推理过程是否有逻辑跳跃",
            "推理结论是否与已知事实矛盾",
            "是否存在循环论证",
        ],
    }
```

### 7.4 科幻小说专属审计

```python
class SciFiChapterAudit:
    """科幻小说每章专属检查 — 围绕设定自洽和科学一致性"""
    
    # ═══════════════════════════════════════════════
    #  追踪表 1: 科技设定一致性表
    # ═══════════════════════════════════════════════
    tech_consistency_table = {
        "name": "科技设定一致性表",
        "columns": [
            "技术名称", "首次出现章节", "能力描述",
            "已建立的限制/代价", "本章使用情况",
            "是否与前文描述一致", "偏差说明",
        ],
        "audit_rules": [
            "本章出现的科技是否都在世界观科技清单中（无凭空冒出的新技术，除非有剧情铺垫）",
            "科技的能力边界是否与前文一致（不能一章说FTL需要一周充能，下一章就秒跳）",
            "科技的代价/限制是否被遵守",
            "新出现的技术是否有合理的引入方式（发现/发明/交易/掠夺）",
            "不同科技之间是否存在逻辑矛盾（如同时存在反重力和牛顿力学场景）",
        ],
    }
    
    # ═══════════════════════════════════════════════
    #  追踪表 2: 社会形态一致性表
    # ═══════════════════════════════════════════════
    society_consistency_table = {
        "name": "社会形态一致性表",
        "columns": [
            "社会要素（政治/经济/阶级/文化/法律）",
            "设定描述", "本章中的体现",
            "是否一致", "偏差说明",
        ],
        "audit_rules": [
            "角色的社会行为是否符合其所处的社会形态",
            "经济系统（货币/交易/资源分配）是否前后一致",
            "权力结构是否稳定或有合理的变化动因",
            "科技水平与社会形态是否匹配（高科技+封建制需有合理解释）",
        ],
    }
    
    # ═══════════════════════════════════════════════
    #  追踪表 3: 物理/宇宙规则表
    # ═══════════════════════════════════════════════
    physics_rules_table = {
        "name": "物理/宇宙规则表",
        "columns": [
            "规则名称", "规则描述",
            "硬度等级（硬/中/软）", "设定章节",
            "本章是否涉及", "是否被遵守",
        ],
        "audit_rules": [
            "FTL/通信/能源等核心物理设定是否保持一致",
            "宇宙尺度（距离/时间）的描述是否自洽",
            "生态环境设定（异星大气/重力/生物）是否前后一致",
            "若有时间旅行/平行宇宙，因果逻辑是否自洽",
        ],
    }
    
    # ═══════════════════════════════════════════════
    #  追踪表 4: 种族/文明档案表
    # ═══════════════════════════════════════════════
    civilization_table = {
        "name": "种族/文明档案表",
        "columns": [
            "种族/文明名", "生理特征", "文化特点",
            "科技水平", "政治态度",
            "与人类关系", "本章表现是否吻合",
        ],
        "audit_rules": [
            "外星种族的行为是否符合其已建立的文化设定",
            "种族间的关系是否符合已建立的政治格局",
            "外星生理特征描写是否前后一致",
            "文明科技水平是否与其行为能力匹配",
        ],
    }
    
    # ═══════════════════════════════════════════════
    #  追踪表 5: 哲学/思想实验进度表
    # ═══════════════════════════════════════════════
    philosophical_progress_table = {
        "name": "哲学/思想实验探讨进度表",
        "columns": [
            "哲学命题", "计划探讨弧线",
            "当前探讨进度", "本章是否推进",
            "通过什么情节/对话推进", "是否过于说教",
        ],
        "audit_rules": [
            "哲学探讨是否通过故事情节自然呈现（而非角色长篇大论）",
            "多个哲学命题的探讨节奏是否均衡",
            "思想实验是否与主线情节有机结合",
        ],
    }
```

### 7.5 玄幻小说专属审计

```python
class XuanhuanChapterAudit:
    """玄幻小说每章专属检查 — 围绕力量体系、爽点节奏、势力平衡"""
    
    # ═══════════════════════════════════════════════
    #  追踪表 1: 修炼进度总表
    # ═══════════════════════════════════════════════
    cultivation_progress_table = {
        "name": "修炼进度总表",
        "columns": [
            "角色名", "当前境界/等级", "上次突破章节",
            "战力评估", "持有功法", "持有法宝",
            "本章境界变化", "变化是否有铺垫",
        ],
        "audit_rules": [
            "主角升级是否有足够的铺垫（修炼/奇遇/感悟）",
            "升级速度是否符合篇幅节奏（不能5章连升3级又50章不动）",
            "配角的实力变化是否合理",
            "降级/实力下降是否有合理原因",
            "本章战斗中角色表现的战力是否与其境界匹配",
            "跨境界战斗（越级战斗）是否有合理的解释和代价",
        ],
    }
    
    # ═══════════════════════════════════════════════
    #  追踪表 2: 势力格局表
    # ═══════════════════════════════════════════════
    faction_table = {
        "name": "势力格局表",
        "columns": [
            "势力名", "势力等级", "掌门/首领",
            "核心强者列表", "与主角关系（敌/友/中立）",
            "势力资源", "本章状态变化",
        ],
        "audit_rules": [
            "势力间的实力对比是否前后一致",
            "势力态度转变是否有合理事件驱动",
            "被灭/重创的势力是否不应再出现",
            "新势力的引入是否有世界观依据",
            "势力等级排序是否与世界观文档一致",
        ],
    }
    
    # ═══════════════════════════════════════════════
    #  追踪表 3: 物品/资源追踪表
    # ═══════════════════════════════════════════════
    item_tracking_table = {
        "name": "物品/资源追踪表",
        "columns": [
            "物品名", "品级/等级", "持有者",
            "获取章节", "获取方式",
            "使用记录", "当前状态（持有/消耗/遗失/赠出）",
        ],
        "audit_rules": [
            "已消耗的丹药/材料不应再次出现在角色持有列表中",
            "法宝的能力表现是否与其品级匹配",
            "物品转手是否有对应情节",
            "储物空间/行囊中的物品清单是否自洽",
            "本章获得的新物品是否有合理来源",
        ],
    }
    
    # ═══════════════════════════════════════════════
    #  追踪表 4: 任务/使命/恩怨追踪表
    # ═══════════════════════════════════════════════
    quest_tracking_table = {
        "name": "任务/使命/恩怨追踪表",
        "columns": [
            "事项描述", "类型（任务/恩怨/承诺/悬念）",
            "发起章节", "涉及角色",
            "当前状态（进行中/已完成/已失败/被遗忘）",
            "预期解决章节", "紧迫度",
        ],
        "audit_rules": [
            "长期未推进的任务/恩怨是否应被提及或推进",
            "已接受的任务是否被遗忘",
            "报仇/报恩等承诺是否在实力允许时被执行",
            "已完成的事项是否不被重复提起为未完成",
            "紧迫事项（如倒计时/追杀）的紧迫感是否在持续体现",
        ],
    }
    
    # ═══════════════════════════════════════════════
    #  追踪表 5: 爽点节奏监控表
    # ═══════════════════════════════════════════════
    shuang_rhythm_table = {
        "name": "爽点节奏监控表",
        "columns": [
            "章节号", "爽点类型", "爽点强度（1-10）",
            "铺垫章节数", "抑→扬转折点",
            "读者情绪曲线标记",
        ],
        "audit_rules": [
            "是否连续超过N章（短篇2章/中篇4章/长篇6章）没有爽点",
            "连续爽点是否导致审美疲劳（不应连续5+章都是高强度爽点）",
            "压抑期是否过长（读者耐心有限）",
            "爽点强度是否呈整体递增趋势（后期爽点不应弱于前期）",
            "打脸/装逼场景是否每次都有新意（不重复同一套路）",
        ],
    }
    
    # ═══════════════════════════════════════════════
    #  追踪表 6: 金手指/外挂使用记录表
    # ═══════════════════════════════════════════════
    golden_finger_log = {
        "name": "金手指使用记录表",
        "columns": [
            "章节号", "使用场景", "使用效果",
            "代价/限制是否体现", "本次使用的合理性",
            "累计使用频率", "是否过度依赖",
        ],
        "audit_rules": [
            "金手指使用是否遵守已建立的限制条件",
            "使用频率是否过高（每章都靠金手指解决问题会减弱角色成长感）",
            "金手指的能力是否有随剧情合理成长（不应一开始就无限强）",
            "关键危机时刻，金手指的表现是否符合其当前等级",
        ],
    }
    
    # ═══════════════════════════════════════════════
    #  追踪表 7: 世界观/修炼规则违规检测
    # ═══════════════════════════════════════════════
    world_rules_table = {
        "name": "世界观规则检测表",
        "columns": [
            "规则名称", "规则描述", "设定章节",
            "本章是否涉及", "是否被遵守", "违规说明",
        ],
        "audit_rules": [
            "修炼体系等级名称/顺序是否与设定一致",
            "境界突破条件（灵石/感悟/天劫/丹药）是否与前文一致",
            "天道/因果/气运等抽象规则是否前后自洽",
            "各境界的寿命设定是否被遵守",
            "禁术/禁忌的设定是否前后一致",
        ],
    }
```

### 7.6 审计执行引擎

```python
class ChapterAuditEngine:
    """章节审计执行引擎"""
    
    async def run_full_audit(self, chapter: Chapter, project: BookProject) -> AuditReport:
        """执行完整审计 = 通用检查 + 题材专属检查"""
        
        report = AuditReport(chapter_id=chapter.id)
        
        # ── 第一步：通用检查 ──
        universal_result = await self._run_universal_audit(chapter, project)
        report.add_section("通用检查", universal_result)
        
        # ── 第二步：题材专属检查 ──
        theme_strategy = project.get_theme_strategy()
        
        # 2a. 获取题材的追踪表当前状态
        current_tables = project.theme_tracking_tables
        
        # 2b. 让 LLM 根据本章内容审计每张追踪表
        for table_def in theme_strategy.get_tracking_table_schema():
            current_data = current_tables.get(table_def.table_id, [])
            table_audit = await self._audit_tracking_table(
                chapter=chapter,
                table_def=table_def,
                current_data=current_data,
                project_context=self._build_audit_context(project),
                theme_strategy=theme_strategy,
            )
            report.add_section(f"题材检查-{table_def.name}", table_audit)
        
        # ── 第三步：更新追踪表 ──
        updated_tables = await theme_strategy.update_tracking_tables(
            tables=current_tables,
            chapter=chapter,
            audit_result=report,
        )
        project.theme_tracking_tables = updated_tables
        
        # ── 第四步：伏笔专项检查 ──
        foreshadow_result = await self._audit_foreshadows(chapter, project)
        report.add_section("伏笔检查", foreshadow_result)
        
        # ── 第五步：综合评分与决策 ──
        report.compute_overall_score()
        report.compute_overall_status()
        report.decision = self._decide_next_action(report)
        
        return report
    
    async def _audit_tracking_table(self, chapter, table_def, current_data,
                                      project_context, theme_strategy) -> TableAuditResult:
        """审计单张追踪表：由题材策略生成专属 prompt，审计引擎只负责执行和校验结构化输出"""
        audit_context = AuditPromptContext(
            table_def=table_def,
            current_rows=current_data,
            project_context=project_context,
            required_output_schema=TableAuditResult,
        )
        prompt = theme_strategy.build_chapter_audit_prompt(chapter, audit_context)
        return await self.llm.generate_structured(prompt, schema=TableAuditResult)
    
    def _decide_next_action(self, report: AuditReport) -> str:
        """把 overall_status 映射为执行决策，避免 pass/fail 与 continue/revise 混用"""
        if report.has_blocking_fail():
            return "revise"
        if report.overall_status == "warning" and report.warning_count > self.config.warning_threshold:
            return "manual_review"
        if report.overall_status == "fail":
            return "revise"
        return "continue"
```

### 7.7 审计报告 GUI 展示

```
┌─────────────────────────────────────────────────────┐
│  📋 第12章审计报告                    总分: 0.85/1.0  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ✅ 通用检查 (5/5 通过)                              │
│  ├── ✅ 角色一致性                                   │
│  ├── ✅ 时间线一致性                                 │
│  ├── ✅ 空间一致性                                   │
│  ├── ✅ 情节逻辑                                     │
│  └── ✅ 叙事质量                                     │
│                                                     │
│  ⚠️ 题材专属检查 (5/7 通过, 2 警告)                   │
│  ├── ✅ 修炼进度总表 — 主角境界无变化，合理             │
│  ├── ✅ 势力格局表 — 无变化                           │
│  ├── ⚠️ 物品/资源追踪表                              │
│  │   └── warning: 第11章已消耗的「凝灵丹」在本章仍被列为持有 │
│  ├── ⚠️ 金手指使用记录表 — 连续3章用于解危，建议增加代价 │
│  └── ✅ 世界观规则检测表 — 未发现违规                   │
│                                                     │
│  ❌ 伏笔检查 (1 项失败)                               │
│  └── fail: 第4章「黑玉令」已超过计划回收窗口5章          │
│                                                     │
│  建议动作: 自动修订 / 人工处理 / 接受警告继续            │
│  [查看追踪表差异] [生成修订稿] [标记人工处理]            │
└─────────────────────────────────────────────────────┘
```

### 7.8 pass / warning / fail 分级与门禁规则

审计报告不只给总分，还必须输出可执行的分级结果。分级用于决定章节是否进入下一步、是否触发自动修订、是否需要人工确认。

| 等级 | 含义 | 处理策略 |
|------|------|----------|
| pass | 检查项完全通过，或仅存在不影响连续性的轻微提示 | 更新追踪表，保存章节，进入下一章 |
| warning | 存在潜在风险，但不一定破坏剧情或设定 | 更新追踪表，记录风险；超过阈值时要求修订或人工确认 |
| fail | 破坏关键连续性、核心设定、题材公平性或章节可读性 | 阻断进入下一章，触发自动修订；连续失败则转人工处理 |

```python
@dataclass
class AuditFinding:
    id: str
    scope: str                    # "universal" | "theme" | "foreshadow" | "style"
    table_name: str | None
    rule: str
    status: Literal["pass", "warning", "fail"]
    detail: str
    evidence: list[str]           # 对应原文片段或追踪表行
    suggested_fix: str | None
    blocking: bool = False


@dataclass
class TablePatch:
    patch_id: str
    table_id: str
    table_name: str
    operation: Literal["insert", "update", "delete", "noop"]
    row_key: str
    base_row_version: int | None
    idempotency_key: str
    before: dict | None
    after: dict | None
    reason: str
    conflict_policy: Literal["reject", "merge", "manual_review"] = "reject"


@dataclass
class TableAuditResult:
    table_id: str
    findings: list[AuditFinding]
    table_patches: list[TablePatch]
    summary: str
    raw_output_hash: str


@dataclass
class AuditReport:
    chapter_id: str
    chapter_no: int
    findings: list[AuditFinding]
    table_patches: list[TablePatch]
    score: float
    overall_status: Literal["pass", "warning", "fail"]
    decision: Literal["continue", "revise", "manual_review"]
    warning_count: int = 0
    fail_count: int = 0
    
    def has_blocking_fail(self) -> bool:
        return any(f.status == "fail" and f.blocking for f in self.findings)
    
    def compute_overall_score(self) -> None:
        weights = {"pass": 1.0, "warning": 0.6, "fail": 0.0}
        self.score = sum(weights[f.status] for f in self.findings) / max(len(self.findings), 1)
    
    def compute_overall_status(self) -> None:
        self.warning_count = sum(1 for f in self.findings if f.status == "warning")
        self.fail_count = sum(1 for f in self.findings if f.status == "fail")
        if self.has_blocking_fail() or self.fail_count > 0:
            self.overall_status = "fail"
        elif self.warning_count > 0:
            self.overall_status = "warning"
        else:
            self.overall_status = "pass"
```

综合判定规则：

1. 任意 `blocking=True` 的 fail，整章 `overall_status=fail`，必须修订。
2. 无 fail 但 warning 数量超过阈值，整章 `overall_status=warning`，由配置决定自动修订或人工确认。
3. 所有追踪表补丁必须先通过幂等校验，再写入项目状态，避免审计重跑造成重复行。
4. 自动修订最多连续执行 2 次；仍 fail 时进入人工处理队列。
5. 每章最终报告随章节快照一起保存，作为后续恢复和远距离对齐的依据。

阻断策略按问题类型分级，而不是所有 warning/fail 一刀切：

| 问题类型 | 默认等级 | 处理策略 |
|----------|----------|----------|
| 角色生死、时间线硬矛盾、核心世界规则被破坏 | blocking fail | 阻断继续生成，优先自动修订，失败后人工确认 |
| 推理解答前必要线索缺失、核心诡计不可行 | blocking fail | 阻断继续生成，必须修订到公平性达标 |
| 科技/修炼/金手指限制被无解释突破 | blocking fail | 阻断继续生成，需补解释、降级表现或改写章节 |
| 风格轻微漂移、节奏偏慢、信息密度偏高 | warning | 记录风险，可在阈值内继续 |
| 爽点间隔偏长、哲学讨论略说教、支线推进偏慢 | warning | 进入待观察列表，连续出现再修订 |
| 读者体验类建议、表达优化建议 | pass/warning | 不阻断，进入修订建议池 |

### 7.9 每章生成后的完整审计流水线

```
生成章节正文
    │
    ▼
通用一致性检查
    │
    ▼
题材专属审计（按题材加载 5-7 张追踪表）
    │
    ▼
生成 pass / warning / fail 分级报告
    │
    ├── fail ─────► 自动修订 / 人工处理
    │
    ├── warning ──► 记录风险，按阈值决定是否修订
    │
    └── pass ─────► 应用追踪表补丁
                       │
                       ▼
                  保存章节快照
                       │
                       ▼
                    进入下一章
```

---

## 八、断点快照

长篇生成任务必须允许中断、迁移、回滚和恢复。v2 的断点系统以“最近章节滚动快照 + 里程碑永久快照”为核心：每章结束后自动保存一次可恢复的逻辑全量快照；普通章节快照只滚动保留最近 N 章，弧线、幕、卷、手动快照永久保留。后续可将物理存储从全量文件演进为增量块或去重存储，但恢复接口始终表现为完整快照。

### 8.1 快照类型与保留策略

| 快照类型 | 触发时机 | 保留策略 | 用途 |
|----------|----------|----------|------|
| chapter | 每章审计通过后 | 默认保留最近 N 章，可配置 | 普通中断恢复、短距离回滚 |
| arc | 每个情节弧结束 | 永久保留 | 弧线级回滚、阶段审校 |
| volume | 每卷结束 | 永久保留 | 跨卷衔接、分卷归档 |
| manual | 用户手动保存 | 默认永久保留，用户可删除 | 重大改动前备份 |
| emergency | 异常退出前自动抢救 | 保留最近 N 个 | 进程崩溃、网络中断后的抢救 |

> 已采纳策略：MVP 使用普通章节滚动保留、里程碑永久保留；当超长篇存储压力明显时，再升级为“逻辑全量、物理增量”的实现。

### 8.2 快照数据模型

```python
@dataclass
class Checkpoint:
    id: str
    project_id: str
    type: Literal["chapter", "arc", "volume", "manual", "emergency"]
    chapter_no: int | None
    arc_id: str | None
    volume_no: int | None
    created_at: datetime
    state_version: str
    payload_uri: str
    content_hash: str
    vector_index_version: str
    style_anchor_hash: str
    audit_report_id: str | None
    retention_policy: Literal["rolling", "permanent", "manual"]
    restore_notes: str | None = None


@dataclass
class CheckpointPayload:
    project_meta: dict
    creation_params: dict
    runtime_config: dict
    world_setting: dict
    characters: list[dict]
    plot_structure: dict
    outline: list[dict]
    chapters: list[dict]
    foreshadowing_registry: list[dict]
    theme_tracking_tables: dict
    memory_layers: dict          # L0/L1/L2/L3 的摘要、索引引用、版本号
    audit_reports: list[dict]
    revision_history: list[dict]
    export_state: dict | None
```

### 8.2.1 章节事件日志

快照负责“某一刻完整状态”，事件日志负责“状态如何变化”。当快照损坏、用户手动编辑历史章节、或需要重建摘要链/追踪表时，系统可以从最近可信快照开始重放事件。

```python
@dataclass
class ChapterEvent:
    id: str
    project_id: str
    chapter_no: int | None
    event_type: Literal[
        "chapter_generated",
        "audit_completed",
        "table_patch_applied",
        "manual_edit",
        "summary_rebuilt",
        "vector_index_updated",
        "checkpoint_created",
    ]
    created_at: datetime
    actor: Literal["system", "user", "llm", "migration"]
    base_checkpoint_id: str | None
    affected_ranges: list[tuple[int, int]]
    payload: dict
    idempotency_key: str
    payload_hash: str
```

事件日志约束：

- 所有会改变项目状态的动作都必须写事件，且事件先于最终状态提交。
- `idempotency_key` 用于避免任务重试时重复应用同一批表格补丁或索引更新。
- `manual_edit` 必须记录受影响章节范围，并触发摘要链、向量索引、追踪表的 dirty 标记。
- 恢复重放只从可信快照开始，按事件时间和依赖顺序应用，不从任意中间事件直接恢复。

### 8.3 快照保存流程

```
章节审计通过 / 里程碑到达
    │
    ▼
冻结当前项目状态（禁止并发写入）
    │
    ▼
收集关系数据 + 文件数据 + 向量索引版本
    │
    ▼
序列化 CheckpointPayload
    │
    ▼
计算 content_hash / style_anchor_hash
    │
    ▼
写入快照存储 + 登记 Checkpoint 元数据
    │
    ▼
执行一次轻量恢复校验（可反序列化、关键字段完整）
    │
    ▼
释放写锁，继续下一章
```

实现约束：

- 快照写入必须是原子操作：元数据、payload、索引版本任一失败都不能标记为可恢复。
- 快照保存与审计报告绑定，恢复后能知道当时有哪些 warning 被接受。
- 每次手动编辑历史章节后，必须生成 manual 快照，并标记受影响章节范围。
- 快照版本需要向后兼容；加载旧版本时通过 migration 将 payload 升级到当前结构。

### 8.4 恢复时的四层上下文重建

恢复不是简单读回 JSON，而是要重建一个可继续写作的 LLM 上下文。系统按四层顺序装配：

#### 第一层：风格锚定

从快照中恢复 `StyleAnchor`，用于锁定叙事声音、句式节奏、描写密度和对话风格。

```python
@dataclass
class StyleAnchor:
    narrative_pov: str
    tone_keywords: list[str]
    diction_notes: list[str]
    pacing_profile: dict
    dialogue_rules: dict
    sample_passages: list[str]       # 代表性原文片段
    forbidden_style_drifts: list[str]
```

恢复时优先注入风格锚点，再注入剧情信息，避免模型先被摘要腔带偏。

#### 第二层：结构摘要

恢复全书结构、当前卷结构、当前弧线目标、章节大纲进度：

- 全书主题和核心承诺
- 已完成卷/弧线摘要
- 当前卷的主线目标、反派压力、高潮设计
- 当前章节在整体结构中的位置
- 下一章必须承接的结构任务

#### 第三层：叙事状态

恢复所有会影响连续性的动态状态：

- 角色状态：位置、伤势、关系、已知信息、目标、持有物
- 时间线状态：当前日期/时刻、倒计时、并行事件
- 伏笔状态：已埋设、已强化、待回收、已回收
- 题材追踪表：推理/科幻/玄幻对应的全部表格
- 审计风险：最近未修复 warning、人工接受的例外

#### 第四层：即时上下文

构造下一章真正要放入 LLM 的工作上下文：

- 前 1-3 章正文或压缩摘要
- 上一章结尾原文片段
- 当前章节大纲、场景清单、情绪目标
- 本章必须使用或禁止使用的信息
- 本章生成后的预期审计重点

```python
class RestoreContextBuilder:
    async def rebuild(self, checkpoint: Checkpoint) -> WritingContext:
        payload = await self.store.load_payload(checkpoint)
        
        style = self._restore_style_anchor(payload)
        structure = self._restore_structural_summary(payload)
        narrative = self._restore_narrative_state(payload)
        immediate = self._build_immediate_context(payload)
        
        context = WritingContext(
            style_anchor=style,
            structural_summary=structure,
            narrative_state=narrative,
            immediate_context=immediate,
        )
        
        await self._validate_restored_context(context, payload)
        return context
```

### 8.5 恢复后的风格一致性验证

恢复完成后，系统必须先生成一小段“续写探针”，再进行风格一致性验证。探针不直接写入正文，只用于判断恢复是否成功。

| 验证项 | 方法 | 失败处理 |
|--------|------|----------|
| 叙事视角 | 静态规则 + LLM 判定 | 重建风格锚点并重试 |
| 句式节奏 | 与代表性章节的句长、段落长度对比 | 增加样本文段 |
| 角色对白 | 与角色语气规则对比 | 注入角色对白样本 |
| 信息边界 | 检查角色是否知道不该知道的事 | 重建叙事状态 |
| 题材口味 | 推理公平性/科幻硬度/玄幻爽点节奏 | 注入题材策略提示 |

```python
@dataclass
class RestoreValidationResult:
    style_score: float
    continuity_score: float
    theme_score: float
    issues: list[str]
    decision: Literal["ready", "manual_confirm", "rebuild_context", "manual_review"]
```

默认阈值采用分段处理：

| 分数区间 | 决策 | 说明 |
|----------|------|------|
| `>= 0.85` | ready | 可继续正式生成 |
| `0.70 - 0.85` | manual_confirm | 显示探针和差异摘要，由用户确认是否继续 |
| `< 0.70` | rebuild_context | 自动重建上下文并重跑验证；连续失败转人工处理 |

`continuity_score` 和 `theme_score` 若涉及 blocking fail，即使总分高于 0.85 也不得直接继续。

评分不能只依赖 LLM 主观判断，必须由“统计指标 + 样本文段 + LLM 复核”共同产生：

```python
@dataclass
class StyleCalibrationProfile:
    sample_chapter_ids: list[str]
    avg_sentence_length: tuple[float, float]   # 均值、允许偏差
    paragraph_length_range: tuple[int, int]
    dialogue_ratio_range: tuple[float, float]
    pov_markers: list[str]
    character_voice_markers: dict[str, list[str]]
    forbidden_markers: list[str]
```

校准流程：

1. 从最近章节、里程碑章节和用户标记的代表章节中抽取样本文段。
2. 用统计指标检查句长、段落长度、对白比例、视角标记和角色口癖。
3. LLM 只负责解释偏差原因和判断是否可接受，不单独决定分数。
4. 用户人工接受的风格变化会写入 `StyleCalibrationProfile`，后续恢复以新基准校验。

低分恢复不直接写入正文；只有 `ready` 或用户确认后的 `manual_confirm` 才能进入正式章节生成。

### 8.6 六种异常场景的容灾策略

| 异常场景 | 风险 | 容灾策略 |
|----------|------|----------|
| 章节生成中断 | 只生成了半章，状态未更新 | 将流式输出写入临时缓冲；恢复时从上一稳定快照继续，临时文本作为可选参考 |
| 审计或追踪表更新失败 | 正文已生成但表格状态不完整 | 审计补丁先写入 staging；全部校验通过后再提交，失败则回滚并重跑审计 |
| 向量索引损坏或丢失 | 远距离检索失效 | 从章节正文、摘要链、追踪表重建索引；重建完成前降级为结构化查询 |
| LLM 调用失败或模型切换 | 生成中断、风格漂移 | 保存当前 prompt 与上下文；切换 Provider 后先跑续写探针和风格验证 |
| 用户手动修改历史章节 | 后续摘要、追踪表、伏笔可能过期 | 标记 dirty range，从最早修改章节起重算摘要链、审计报告和追踪表 |
| 快照文件与数据库不一致 | 恢复到损坏或混杂状态 | 使用 content_hash 校验；失败时回退到最近里程碑快照，并按章节事件日志重放 |

### 8.7 恢复入口与用户体验

GUI 中提供“恢复到此处”入口，但默认只展示可信快照：

```
┌──────────────────────────────────────────────┐
│  断点快照                                     │
├──────────────────────────────────────────────┤
│  永久  卷一结束     第48章  2026-05-25 20:10  │
│  永久  第一幕结束   第18章  2026-05-25 18:42  │
│  最近  第52章通过   第52章  2026-05-25 21:08  │
│  最近  第51章通过   第51章  2026-05-25 20:54  │
│                                              │
│  [查看差异] [恢复到此处] [导出快照]             │
└──────────────────────────────────────────────┘
```

恢复前必须显示差异摘要：

- 将丢弃哪些后续章节
- 哪些追踪表会回滚
- 哪些人工编辑会被覆盖
- 恢复后从哪一章继续生成

---

## 九、超长跨度对齐

超长篇的问题不是“记不住上一章”，而是“几百章前的细节是否仍然约束现在”。v2 采用三路并行定位 + 定期全局扫描 + 分卷隔离与跨卷桥接，保证远距离情节、设定、角色和风格不漂移。

### 9.1 远距离内容定位：三路并行

当生成或审计需要查找远处内容时，系统同时启动三条检索路径，再合并结果：

```
对齐查询（角色/设定/伏笔/物品/地点/风格）
    │
    ├── 向量检索：找语义相近的旧章节、旧场景、旧对白
    │
    ├── 结构化查询：查角色表、时间线、伏笔表、题材追踪表
    │
    └── 摘要链追溯：从全书→卷→弧→章逐级定位原始章节
          │
          ▼
      合并去重 + 可信度排序
          │
          ▼
      注入写作上下文 / 审计上下文
```

```python
@dataclass
class AlignmentQuery:
    query_type: Literal["character", "timeline", "foreshadow", "setting", "item", "style"]
    natural_language_query: str
    entities: list[str]
    current_chapter_no: int
    search_scope: dict              # volume、arc、chapter range、theme table 等
    max_results: int = 12


@dataclass
class AlignmentHit:
    source: Literal["vector", "structured", "summary_chain"]
    chapter_no: int | None
    entity_id: str | None
    evidence: str
    confidence: float
    freshness: Literal["current_volume", "previous_volume", "global"]
    payload: dict


class LongRangeAlignmentService:
    async def locate(self, query: AlignmentQuery) -> list[AlignmentHit]:
        vector_hits, structured_hits, summary_hits = await gather(
            self.vector_retriever.search(query),
            self.structured_store.query(query),
            self.summary_chain.trace(query),
        )
        return self.rank_and_merge(vector_hits, structured_hits, summary_hits)
```

三路结果的可信度优先级：

1. 结构化追踪表和时间线优先于自然语言摘要。
2. 原文章节证据优先于二级摘要。
3. 最近一次人工确认的状态优先于自动推断状态。
4. 当前卷状态优先于旧卷状态，但跨卷桥接字段可提升旧卷约束优先级。

### 9.2 摘要链设计

摘要链用于快速从宏观定位到原文，避免每次都检索全书。

```
BookSummary
  └── VolumeSummary[]
        └── ArcSummary[]
              └── ChapterSummary[]
                    └── SceneSummary[]
```

每层摘要都必须包含：

- 本层发生的关键事件
- 角色状态变化
- 新增或变化的设定
- 伏笔埋设/强化/回收
- 题材追踪表变更摘要
- 指向下层或原文的稳定 ID

```python
@dataclass
class SummaryNode:
    id: str
    level: Literal["book", "volume", "arc", "chapter", "scene"]
    parent_id: str | None
    chapter_range: tuple[int, int]
    summary: str
    entities: list[str]
    state_changes: list[dict]
    foreshadow_refs: list[str]
    table_patch_refs: list[str]
    source_refs: list[str]
    embedding_id: str
```

### 9.3 定期全局扫描

超长篇不能只依赖每章局部审计，还要定期执行全局扫描。扫描不一定重写正文，但必须输出问题清单、影响范围和建议修复方式。

| 扫描项 | 检查目标 | 典型问题 |
|--------|----------|----------|
| 角色存活校验 | 死亡、失踪、离队、重伤角色是否被正确处理 | 已死亡角色在后文无解释出现 |
| 时间线校验 | 主线、支线、并行事件的日期和顺序 | 两地事件耗时不可能、倒计时失效 |
| 伏笔超期 | 伏笔是否超过计划回收窗口 | 关键物件被遗忘 80 章 |
| 设定漂移 | 世界规则、科技规则、修炼规则是否变形 | 早期限制被后期无解释突破 |
| 风格漂移 | 叙事声音、对白口吻、章节节奏是否偏移 | 中后期突然变成另一种文风 |
| 题材节奏 | 推理公平性、科幻思想线、玄幻爽点节奏是否达标 | 推理线索不足、爽点断档、哲学线说教 |

扫描频率建议：

| 篇幅 | 自动扫描频率 | 强制扫描节点 |
|------|--------------|--------------|
| 中篇 | 每幕结束 | 完稿前 |
| 长篇 | 每 10 章 + 每卷结束 | 卷结束、重大反转前 |
| 超长篇 | 每 5-8 章 + 每弧结束 + 每卷结束 | 跨卷前、跨大地图前、最终章前 |

```python
class GlobalConsistencyScanner:
    async def scan(self, project: BookProject, scope: ScanScope) -> GlobalScanReport:
        checks = [
            self._scan_character_liveness,
            self._scan_timeline,
            self._scan_overdue_foreshadows,
            self._scan_setting_drift,
            self._scan_style_drift,
            self._scan_theme_rhythm,
        ]
        
        results = [await check(project, scope) for check in checks]
        return GlobalScanReport.merge(results)
```

### 9.4 分卷隔离机制

超长篇按卷组织，每卷拥有相对独立的记忆空间，降低上下文污染。

```python
@dataclass
class VolumeMemorySpace:
    volume_no: int
    volume_title: str
    chapter_range: tuple[int, int]
    local_vector_namespace: str
    local_tracking_tables: dict
    local_character_states: dict
    local_plot_threads: list[dict]
    local_style_notes: dict
    sealed: bool = False
```

分卷隔离原则：

- 当前卷生成时，默认检索当前卷记忆空间。
- 旧卷内容只有通过跨卷桥接、全局设定、全局角色状态或显式检索请求才进入上下文。
- 卷结束后将本卷状态封存，禁止后续章节直接修改旧卷追踪表。
- 若用户修改旧卷正文，必须重新生成该卷的 VolumeBridge，并标记后续卷需要重新对齐。

### 9.5 跨卷桥接 VolumeBridge

每卷结束时生成精简的 `VolumeBridge`，传递给下一卷。它不是全卷摘要，而是下一卷必须知道的“约束包”。

```python
@dataclass
class VolumeBridge:
    from_volume: int
    to_volume: int
    bridge_version: str
    
    volume_resolution: str              # 本卷完成了什么
    active_characters: list[dict]        # 仍会影响后续的角色及状态
    removed_characters: list[dict]       # 死亡/离场/封印等不可误用角色
    unresolved_threads: list[dict]       # 未完主线、支线、恩怨、任务
    cross_volume_foreshadows: list[dict] # 跨卷伏笔及回收计划
    global_rule_updates: list[dict]      # 新增或变化的世界规则
    item_transfers: list[dict]           # 重要物品归属
    relationship_changes: list[dict]     # 关系格局变化
    style_anchor_delta: dict             # 本卷形成的风格变化
    forbidden_contradictions: list[str]  # 下一卷绝不能违反的事实
    next_volume_hooks: list[str]         # 下一卷开篇可承接的钩子
```

生成流程：

```
卷末章节审计通过
    │
    ▼
执行本卷全局扫描
    │
    ▼
冻结 VolumeMemorySpace
    │
    ▼
提取跨卷约束与未完成事项
    │
    ▼
生成 VolumeBridge
    │
    ▼
桥接审计：检查是否遗漏关键状态
    │
    ▼
创建下一卷初始记忆空间
```

VolumeBridge 的确认策略：

| 项目规模 | 确认方式 | 原因 |
|----------|----------|------|
| 短篇/中篇 | 默认自动生成，无需强制确认 | 跨卷风险低，保持流程顺畅 |
| 长篇 | 卷末建议人工确认，可跳过 | 跨卷约束开始复杂，人工确认能降低后续返工 |
| 超长篇 | 卷末必须人工确认 | 跨卷桥接会影响数百章，遗漏成本高 |

人工确认界面必须突出 `removed_characters`、`unresolved_threads`、`cross_volume_foreshadows`、`forbidden_contradictions` 四类高风险字段；用户确认后的桥接内容写入事件日志，优先级高于自动推断。

### 9.6 下一卷启动上下文

下一卷开写时，不直接塞入上一卷全文，而是装配：

1. 全书级 BookBible：核心主题、世界底层规则、主角长期弧线。
2. 上一卷 VolumeBridge：跨卷约束包。
3. 下一卷 VolumePlan：本卷目标、主要冲突、阶段高潮。
4. 当前卷空白追踪表：只继承跨卷必要行。
5. 风格锚点：全书稳定风格 + 上一卷允许保留的风格变化。

这样既能保留远距离连续性，又不会让旧卷大量细节淹没当前卷创作。

### 9.7 远距离对齐的阻断条件

当全局扫描或三路检索发现以下情况时，必须阻断继续生成：

- 关键角色生死状态矛盾。
- 主线时间线出现不可调和冲突。
- 核心世界规则被无解释推翻。
- 推理小说的必要线索未在解答前公平呈现。
- 科幻小说的核心科技限制被随意突破。
- 玄幻小说的境界、资源、金手指使用破坏成长闭环。
- 跨卷桥接中标记为 `forbidden_contradictions` 的事实被违反。

阻断后的处理顺序：

1. 定位最早冲突点。
2. 计算影响章节范围。
3. 优先尝试局部修订当前章或最近章节。
4. 若冲突来自旧摘要或追踪表错误，重建摘要链和表格。
5. 若冲突来自正文硬矛盾，提交人工确认。

---

## 十、测试与验收策略

这个项目的核心风险在“生成看起来合理，但状态已经悄悄错了”。因此测试不能只覆盖 API 是否返回成功，还要覆盖审计、恢复、对齐和人工编辑后的状态重建。

### 10.1 审计测试集

为三类题材分别维护固定 fixture：

| 题材 | 必测场景 | 验收标准 |
|------|----------|----------|
| 推理 | 线索缺失、嫌疑人排除不充分、时间线矛盾、解答前必要线索不足 | 能输出对应 fail，并定位到线索表/嫌疑人表/时间线表 |
| 科幻 | 科技限制被突破、社会制度前后矛盾、物理规则漂移 | 能区分硬错误和可解释外推 |
| 玄幻 | 境界跳升、物品重复出现、金手指过度使用、势力状态错误 | 能生成表格补丁并阻断关键违规章节 |

### 10.2 快照与恢复测试

```python
class CheckpointGoldenTests:
    async def test_restore_same_state(self):
        """从章节快照恢复后，世界观/角色/追踪表/伏笔状态 hash 必须一致"""

    async def test_replay_from_event_log(self):
        """从最近里程碑快照 + 事件日志重放，结果应与最新快照一致"""

    async def test_manual_edit_dirty_range(self):
        """手动修改历史章节后，应标记受影响摘要、索引和追踪表为 dirty"""
```

验收标准：

- 同一快照连续恢复 3 次，关键状态 hash 一致。
- 删除向量索引后可从正文和摘要链重建，检索结果通过最低召回率要求。
- 模型切换后必须通过续写探针和风格校准，才能继续正式生成。

### 10.3 远距离对齐测试

| 测试项 | 方法 | 最低要求 |
|--------|------|----------|
| 向量检索召回 | 给定角色、物品、伏笔查询，检查是否召回原章节 | Top 10 召回率 >= 0.85 |
| 结构化查询准确性 | 查询角色生死、物品归属、任务状态 | 准确率 >= 0.98 |
| 摘要链追溯 | 从卷摘要定位到章节和场景 | 定位误差不超过 1 章 |
| VolumeBridge 回归 | 下一卷引用上一卷约束 | 不违反 forbidden_contradictions |

### 10.4 人工编辑回归测试

人工编辑是最容易破坏自动状态的入口，必须单独验收：

1. 修改旧章节角色生死状态后，后续角色表和 VolumeBridge 必须标记需重建。
2. 删除旧章节线索后，推理公平性审计必须重新计算。
3. 改写科技限制后，科幻规则表和设定漂移扫描必须更新。
4. 修改玄幻境界或物品归属后，修炼进度表和物品流转表必须重算。

### 10.5 性能与成本验收

| 场景 | 指标 |
|------|------|
| 单章生成 + 审计 | 普通长篇章节应在可配置超时内完成，失败可安全重试 |
| 全局扫描 | 超长篇扫描应支持后台任务，不阻塞 GUI 基本操作 |
| 快照保存 | 每章快照保存必须原子完成，失败不得污染最新可恢复状态 |
| LLM 调用 | 每次生成记录 token、模型、费用估算和重试次数 |

### 10.6 后台任务队列验收

| 测试项 | 验收标准 |
|--------|----------|
| 暂停/继续 | 章节生成任务暂停后不再提交新状态，继续后从最近安全步骤恢复 |
| 取消 | 取消任务不会破坏已提交章节、审计报告和快照 |
| 重试 | 同一 `idempotency_key` 的审计补丁和快照写入不会重复生效 |
| 并发锁 | 同一项目不能同时运行两个写状态任务 |
| 后台扫描 | 全局扫描运行时 GUI 可继续浏览、编辑和查看已有报告 |

---

## 十一、阶段性实施建议

为降低一次性实现复杂度，建议按以下顺序开发：

| 阶段 | 目标 | 完成标志 |
|------|------|----------|
| M1 | 基础项目创建、体裁/题材策略接口、章节生成闭环 | 可创建小说项目并生成前 3 章 |
| M2 | 通用记忆系统与伏笔管理 | 中篇项目能保持角色、时间线、伏笔一致 |
| M3 | 第七章题材专属审计 | 推理/科幻/玄幻均能生成追踪表和分级报告 |
| M4 | 第八章断点快照 | 任意章节后可恢复，并通过风格一致性验证 |
| M5 | 第九章超长跨度对齐 | 长篇/超长篇支持全局扫描与 VolumeBridge |
| M6 | GUI 完整化、导出、人工审校工作流 | 用户可从创建到导出完成一本书 |
