"""Source-bound reimbursement tiers; headings stay attached to their amounts."""
import re


def benefit_tiers(blocks):
    result=[]
    context=None
    context_block=None
    for block in blocks:
        text=re.sub(r"\s+","",block["text"])
        if re.match(r"^[一二三四五六七八九十、()（）\d.]*一般青年",text):
            context="一般對象";context_block=block
        elif re.match(r"^[一二三四五六七八九十、()（）\d.]*文化語言保存者",text):
            context="文化語言保存者";context_block=block
        elif re.match(r"^[一二三四五六七八九十、()（）\d.]*特定對象",text):
            context="特定對象";context_block=block
        if not re.search(r"最高|上限",text) or not re.search(r"補助|青年",text):continue
        for clause in re.split(r"[；。]",text):
            match=re.search(r"(?:最高補助以|上限|最高)[^\d]{0,18}([\d,]+)元",clause)
            if not match:continue
            if re.search(r"低收入|中低收入",clause):tier="低收／中低收加額"
            elif re.search(r"文化語言保存者",clause):tier="文化語言保存者"
            elif re.search(r"特定對象",clause):tier="特定對象"
            elif "一般青年" in clause or "每人每年" in clause:tier="一般對象"
            else:tier=context or "對象待核"
            percentage=re.search(r"(\d+)%",clause)
            label=tier+(f"（補助比例{percentage[1]}%）" if percentage else "")
            refs=[block]
            if context_block and context_block!=block and tier==context:refs.append(context_block)
            result.append({"label":label,"amount_max":int(match[1].replace(",","")),"blocks":refs})
    return result
