#!/usr/bin/env python3
"""
人物传记生成流程测试脚本

验证 BIO01→BIO05 的完整流程
"""

import json
import time
import sys
from pathlib import Path

# 添加项目根到路径
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.services import service_manager, session_store


# ── 测试数据 ────────────────────────────────────────
TEST_FORM_DATA = {
    "deceased_name": "陈文斌",
    "deceased_gender": "男",
    "birth_date": "1948年10月15日",
    "death_date": "2025年4月8日",
    "occupation": "退休工程师（原上海机床厂车间主任、某机械制造公司技术部经理）",
    "family_memory_text": (
        "父亲是一个话不多但做什么都认真到底的人。青年时戴黑框眼镜，穿蓝色中山装，"
        "眼神里总有一种让人安心的笃定。退休后每天清晨和母亲去公园打太极拳，风雨无阻，"
        "说「动起来才有精气神」。他爱好书法多年，书法作品多次在社区展览中获奖；"
        "还坚持集邮，把每一枚邮票都仔细收进册子，说「小小方寸，装着大世界」。"
        "2020年起成为社区志愿者，帮邻里修电器、疏通水管、调解纠纷，从不推辞，"
        "说「退休了更要做点有用的事」。\n\n"
        "事迹一：1968年响应上山下乡号召赴安徽阜阳插队，十年知青岁月中学会种地、木工、电工，"
        "1978年高考恢复以优异成绩考上上海工业大学机械工程系，是全公社唯一考上大学的知青。\n"
        "事迹二：1990年担任上海机床厂车间主任，带领团队攻克多项技术难关，"
        "1985年起连续多年被评为厂级先进工作者，同事们都叫他「陈工」。\n"
        "事迹三：1975年在安徽阜阳与母亲李秀英举办简朴婚礼，相伴五十年从未分离，"
        "2025年迎来金婚纪念。\n"
        "事迹四：孙女陈雨桐高考前，父亲每天为她备好夜宵放在书桌旁，从不打扰，"
        "只在门缝里静静看一眼，说「孩子努力，我们陪着就够了」。"
    ),
    "last_wishes": "希望家人身体健康、和和睦睦，盼孙女陈雨桐学业顺遂。",
}


def print_section(title: str):
    """打印分隔符"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def main():
    print_section("念念平台 - 人物传记生成测试")
    
    # 1. 创建 Session
    print("📝 步骤 1: 创建 Session...")
    sid = session_store.create_session(TEST_FORM_DATA)
    print(f"✓ Session 已创建: {sid}\n")
    
    # 2. 执行 BIO01 - 素材提取
    print("📝 步骤 2: 执行 BIO01 - 素材信息提取...")
    t0 = time.time()
    result_bio01 = service_manager.run_bio_step(sid, "BIO01")
    elapsed = time.time() - t0
    
    if result_bio01.get("error"):
        print(f"❌ BIO01 失败: {result_bio01.get('message')}")
        return 1
    
    print(f"✓ BIO01 完成 ({elapsed:.2f}s)")
    s = session_store.require(sid)
    extracted_count = len(s["bio_state"].get("extracted_chunks", []))
    print(f"  → 提取信息块: {extracted_count} 条\n")
    
    # 3. 执行 BIO02 - 信息审核
    print("📝 步骤 3: 执行 BIO02 - 信息可用性审核...")
    t0 = time.time()
    result_bio02 = service_manager.run_bio_step(sid, "BIO02")
    elapsed = time.time() - t0
    
    if result_bio02.get("error"):
        print(f"❌ BIO02 失败: {result_bio02.get('message')}")
        return 1
    
    print(f"✓ BIO02 完成 ({elapsed:.2f}s)")
    s = session_store.require(sid)
    usable_count = len(s["bio_state"].get("usable_chunks", []))
    gaps_count = len(s["bio_state"].get("info_gaps", []))
    print(f"  → 可用信息块: {usable_count} 条")
    print(f"  → 信息缺口: {gaps_count} 处\n")
    
    # 4. 执行 BIO03 - 时间线重建
    print("📝 步骤 4: 执行 BIO03 - 时间线重建...")
    t0 = time.time()
    result_bio03 = service_manager.run_bio_step(sid, "BIO03")
    elapsed = time.time() - t0
    
    if result_bio03.get("error"):
        print(f"❌ BIO03 失败: {result_bio03.get('message')}")
        return 1
    
    print(f"✓ BIO03 完成 ({elapsed:.2f}s)")
    s = session_store.require(sid)
    timeline_events = len(s["bio_state"].get("timeline", []))
    print(f"  → 时间线事件: {timeline_events} 条\n")
    
    # 5. 执行 BIO04 - 传记文本生成
    print("📝 步骤 5: 执行 BIO04 - 传记文本生成（核心）...")
    t0 = time.time()
    result_bio04 = service_manager.run_bio_step(sid, "BIO04")
    elapsed = time.time() - t0
    
    if result_bio04.get("error"):
        print(f"❌ BIO04 失败: {result_bio04.get('message')}")
        return 1
    
    print(f"✓ BIO04 完成 ({elapsed:.2f}s)")
    s = session_store.require(sid)
    bio_draft = s["bio_state"].get("bio_draft", "")
    word_count = len(bio_draft)
    print(f"  → 传记字数: ~{word_count} 字\n")
    
    # 6. 执行 BIO05 - 质量评审
    print("📝 步骤 6: 执行 BIO05 - 质量评审与润色...")
    t0 = time.time()
    result_bio05 = service_manager.run_bio_step(sid, "BIO05")
    elapsed = time.time() - t0
    
    if result_bio05.get("error"):
        print(f"❌ BIO05 失败: {result_bio05.get('message')}")
        return 1
    
    print(f"✓ BIO05 完成 ({elapsed:.2f}s)")
    s = session_store.require(sid)
    bio_final = s["bio_state"].get("bio_final", "")
    quality_score = s["bio_state"].get("quality_assessment", {}).get("overall_score", "N/A")
    print(f"  → 最终传记字数: ~{len(bio_final)} 字")
    print(f"  → 质量评分: {quality_score}/10\n")
    
    # 7. 获取最终结果
    print("📝 步骤 7: 获取最终结果...")
    result = service_manager.get_biography_result(sid)
    
    if result.get("error"):
        print(f"❌ 获取结果失败: {result.get('message')}")
        return 1
    
    print("✓ 传记生成完成！\n")
    
    # 8. 输出最终传记摘要
    print_section("📖 最终传记摘要（前500字）")
    bio_final = result.get("biography_final", "")
    print(bio_final[:500] + "...\n")
    
    # 9. 输出结果统计
    print_section("📊 生成结果统计")
    print(f"Session ID: {sid}")
    print(f"总字数: {len(bio_final)} 字")
    print(f"质量评分: {quality_score}/10")
    print(f"时间线事件: {len(result.get('timeline', []))} 条")
    print(f"信息缺口: {len(result.get('info_gaps', []))} 处")
    
    # 10. 保存到文件
    output_file = Path(__file__).parent / f"biography_test_{sid[:8]}.md"
    output_file.write_text(bio_final, encoding="utf-8")
    print(f"\n✓ 传记已保存到: {output_file}\n")
    
    print_section("✅ 测试完成！")
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
