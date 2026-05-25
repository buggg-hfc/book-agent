from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class TrackingColumnDef:
    key: str
    label: str
    type: Literal["string", "number", "enum", "chapter_ref", "entity_ref", "list", "object"]
    required: bool = False
    enum_values: list[str] | None = None


@dataclass(frozen=True)
class TrackingTableDef:
    table_id: str
    name: str
    primary_key: str
    unique_keys: list[list[str]]
    columns: list[TrackingColumnDef]
    audit_rules: list[str]
    merge_policy: Literal["append_only", "upsert_by_pk", "manual_on_conflict"] = "upsert_by_pk"


def col(key: str, label: str, typ: str = "string", required: bool = False) -> TrackingColumnDef:
    return TrackingColumnDef(key=key, label=label, type=typ, required=required)  # type: ignore[arg-type]


class ThemeStrategy:
    theme: str = "generic"
    display_name: str = "通用"

    def tracking_tables(self) -> list[TrackingTableDef]:
        raise NotImplementedError

    def seed_tracking_tables(self) -> dict[str, list[dict[str, Any]]]:
        return {table.table_id: [] for table in self.tracking_tables()}

    def outline_seed(self) -> list[str]:
        return ["开端", "推进", "转折", "高潮", "收束"]

    def build_chapter_text(self, project: dict[str, Any], chapter_no: int) -> tuple[str, str]:
        title = f"第{chapter_no}章 线索推进"
        idea = project["creation_params"].get("core_idea", "一个尚未命名的故事")
        return title, (
            f"第{chapter_no}章围绕「{idea}」继续推进。\n\n"
            f"主角在本章重新确认目标，和关键角色交换信息，并留下一个可审计的状态变化。"
            f"本章保持既定叙事视角，承接上一章结尾，为下一章准备新的冲突。"
        )

    def table_updates(self, chapter_no: int) -> dict[str, list[dict[str, Any]]]:
        return {}

    def build_chapter_audit_prompt(self, chapter: Any, audit_context: Any) -> str:
        rules = "\n".join(f"- {rule}" for rule in audit_context.table_def.audit_rules)
        return (
            f"请审计章节《{chapter.title}》与追踪表「{audit_context.table_def.name}」的一致性。\n"
            f"审计规则：\n{rules}\n"
            f"当前行数：{len(audit_context.current_rows)}\n"
            "请输出 pass/warning/fail 和 TablePatch JSON。"
        )

    def update_tracking_tables(self, tables: dict[str, list[dict[str, Any]]], patches: list[Any]) -> dict[str, list[dict[str, Any]]]:
        for patch in patches:
            rows = tables.setdefault(patch.table_id, [])
            if patch.operation in {"insert", "update"} and patch.after:
                existing = next((row for row in rows if row.get("_row_key") == patch.row_key), None)
                if existing:
                    existing.update(patch.after)
                else:
                    row = dict(patch.after)
                    row["_row_key"] = patch.row_key
                    rows.append(row)
        return tables


class MysteryStrategy(ThemeStrategy):
    theme = "mystery"
    display_name = "推理"

    def outline_seed(self) -> list[str]:
        return ["案件发生", "初步调查", "嫌疑格局变化", "关键线索重读", "逻辑解答"]

    def tracking_tables(self) -> list[TrackingTableDef]:
        return [
            TrackingTableDef("mystery.clues", "线索追踪表", "clue_id", [["description", "first_chapter"]], [
                col("clue_id", "线索ID", required=True),
                col("description", "线索描述", required=True),
                col("first_chapter", "首次出现章节", "chapter_ref"),
                col("type", "类型"),
                col("status", "当前状态"),
            ], ["新线索必须入表", "误导线索必须有排除理由"]),
            TrackingTableDef("mystery.suspects", "嫌疑人状态表", "suspect_id", [["name"]], [
                col("suspect_id", "嫌疑人ID", required=True),
                col("name", "角色名", required=True),
                col("suspicion", "嫌疑等级"),
                col("motive", "动机"),
                col("alibi", "不在场证明"),
            ], ["嫌疑等级变化需要证据支撑"]),
            TrackingTableDef("mystery.timeline", "作案时间线对照表", "event_id", [["time_label", "actor"]], [
                col("event_id", "事件ID", required=True),
                col("time_label", "时间点"),
                col("actor", "角色"),
                col("known_to_detective", "侦探已知信息"),
                col("known_to_reader", "读者已知信息"),
            ], ["时间线新信息必须与真实时间线吻合"]),
            TrackingTableDef("mystery.trick", "诡计完整性表", "trick_part_id", [["element"]], [
                col("trick_part_id", "诡计要素ID", required=True),
                col("element", "诡计要素"),
                col("clue_chapter", "线索所在章节", "chapter_ref"),
                col("fairness", "公平性"),
            ], ["核心诡计要素必须有对应线索"]),
            TrackingTableDef("mystery.reasoning", "推理逻辑链表", "step_id", [["step_no"]], [
                col("step_id", "推理步骤ID", required=True),
                col("step_no", "步骤编号", "number"),
                col("premise", "前提"),
                col("conclusion", "结论"),
            ], ["推理步骤不能有逻辑跳跃"]),
        ]

    def build_chapter_text(self, project: dict[str, Any], chapter_no: int) -> tuple[str, str]:
        title = f"第{chapter_no}章 新的证词"
        idea = project["creation_params"].get("core_idea", "一个案件")
        return title, (
            f"第{chapter_no}章中，侦探围绕「{idea}」重新询问证人。\n\n"
            "一枚带灰尘的钥匙被记录为线索，嫌疑人的不在场证明出现裂缝。"
            "叙述只呈现侦探已经获得的信息，读者也能看到同一组证据。"
        )

    def table_updates(self, chapter_no: int) -> dict[str, list[dict[str, Any]]]:
        return {
            "mystery.clues": [{
                "clue_id": f"clue-{chapter_no}",
                "description": f"第{chapter_no}章出现的钥匙灰尘",
                "first_chapter": chapter_no,
                "type": "真实",
                "status": "已呈现",
                "_row_version": 1,
            }],
            "mystery.suspects": [{
                "suspect_id": "suspect-main",
                "name": "主要嫌疑人",
                "suspicion": "中",
                "motive": "与受害者存在旧怨",
                "alibi": "存疑",
                "_row_version": chapter_no,
            }],
        }


class SciFiStrategy(ThemeStrategy):
    theme = "sci_fi"
    display_name = "科幻"

    def outline_seed(self) -> list[str]:
        return ["技术出现", "社会反应", "限制暴露", "思想冲突", "选择后果"]

    def tracking_tables(self) -> list[TrackingTableDef]:
        return [
            TrackingTableDef("scifi.tech", "科技设定表", "tech_id", [["name"]], [
                col("tech_id", "技术ID", required=True), col("name", "技术名称"), col("limits", "限制"), col("status", "状态")
            ], ["技术能力边界必须一致"]),
            TrackingTableDef("scifi.society", "社会形态表", "society_id", [["aspect"]], [
                col("society_id", "社会要素ID", required=True), col("aspect", "社会要素"), col("description", "设定描述")
            ], ["社会行为必须符合社会形态"]),
            TrackingTableDef("scifi.physics", "物理规则表", "rule_id", [["name"]], [
                col("rule_id", "规则ID", required=True), col("name", "规则名称"), col("hardness", "硬度等级")
            ], ["核心物理规则必须被遵守"]),
            TrackingTableDef("scifi.civilizations", "文明档案表", "civ_id", [["name"]], [
                col("civ_id", "文明ID", required=True), col("name", "文明名"), col("tech_level", "科技水平")
            ], ["文明行为能力应匹配科技水平"]),
            TrackingTableDef("scifi.philosophy", "哲学探讨进度表", "topic_id", [["topic"]], [
                col("topic_id", "命题ID", required=True), col("topic", "哲学命题"), col("progress", "进度")
            ], ["哲学探讨应通过情节推进"]),
        ]

    def build_chapter_text(self, project: dict[str, Any], chapter_no: int) -> tuple[str, str]:
        return f"第{chapter_no}章 技术的边界", (
            "新的核心技术在本章被用于解决危机，但它的能量限制也被明确记录。"
            "角色围绕技术代价发生争执，社会结构的压力开始显形。"
        )

    def table_updates(self, chapter_no: int) -> dict[str, list[dict[str, Any]]]:
        return {"scifi.tech": [{
            "tech_id": "tech-core",
            "name": "核心跃迁技术",
            "limits": "需要长时间充能",
            "status": f"第{chapter_no}章使用后进入冷却",
            "_row_version": chapter_no,
        }]}


class XuanhuanStrategy(ThemeStrategy):
    theme = "xuanhuan"
    display_name = "玄幻"

    def outline_seed(self) -> list[str]:
        return ["低谷受辱", "奇遇入门", "资源争夺", "越级挑战", "进入更大世界"]

    def tracking_tables(self) -> list[TrackingTableDef]:
        return [
            TrackingTableDef("xuanhuan.cultivation", "修炼进度表", "character_id", [["name"]], [
                col("character_id", "角色ID", required=True), col("name", "角色名"), col("realm", "当前境界"), col("battle_power", "战力评估")
            ], ["升级必须有铺垫"]),
            TrackingTableDef("xuanhuan.factions", "势力格局表", "faction_id", [["name"]], [
                col("faction_id", "势力ID", required=True), col("name", "势力名"), col("attitude", "与主角关系")
            ], ["势力态度转变需要事件驱动"]),
            TrackingTableDef("xuanhuan.items", "物品流转表", "item_id", [["name", "owner"]], [
                col("item_id", "物品ID", required=True), col("name", "物品名"), col("owner", "持有者"), col("status", "状态")
            ], ["已消耗物品不能重复出现"]),
            TrackingTableDef("xuanhuan.quests", "任务恩怨表", "quest_id", [["description"]], [
                col("quest_id", "事项ID", required=True), col("description", "事项描述"), col("status", "状态")
            ], ["长期事项不能被遗忘"]),
            TrackingTableDef("xuanhuan.rhythm", "爽点节奏表", "chapter_no", [["chapter_no"]], [
                col("chapter_no", "章节号", "number", required=True), col("type", "爽点类型"), col("strength", "强度", "number")
            ], ["爽点节奏不能长期断档"]),
            TrackingTableDef("xuanhuan.golden_finger", "金手指使用表", "use_id", [["chapter_no"]], [
                col("use_id", "使用ID", required=True), col("chapter_no", "章节号", "number"), col("cost", "代价")
            ], ["金手指使用必须体现限制"]),
            TrackingTableDef("xuanhuan.world_rules", "世界观规则检测表", "rule_id", [["name"]], [
                col("rule_id", "规则ID", required=True), col("name", "规则名称"), col("status", "是否遵守")
            ], ["修炼规则必须前后一致"]),
        ]

    def build_chapter_text(self, project: dict[str, Any], chapter_no: int) -> tuple[str, str]:
        return f"第{chapter_no}章 初试锋芒", (
            "主角通过前文铺垫获得的资源完成一次小突破，但仍付出明显代价。"
            "敌对势力的态度变化被记录，金手指只提供辅助，不能替代主角行动。"
        )

    def table_updates(self, chapter_no: int) -> dict[str, list[dict[str, Any]]]:
        return {
            "xuanhuan.cultivation": [{
                "character_id": "hero",
                "name": "主角",
                "realm": f"第{chapter_no}层",
                "battle_power": "稳步提升",
                "_row_version": chapter_no,
            }],
            "xuanhuan.rhythm": [{
                "chapter_no": chapter_no,
                "type": "小胜",
                "strength": min(10, 4 + chapter_no),
                "_row_version": 1,
            }],
        }


STRATEGIES: dict[str, ThemeStrategy] = {
    "mystery": MysteryStrategy(),
    "sci_fi": SciFiStrategy(),
    "xuanhuan": XuanhuanStrategy(),
}


def get_strategy(theme: str) -> ThemeStrategy:
    return STRATEGIES.get(theme, STRATEGIES["mystery"])
