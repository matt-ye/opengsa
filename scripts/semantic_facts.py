"""Conservative clause discovery shared by every source; no URLs, providers or fetches."""
import re

INSTRUCTIONS = (
    '先辨識文件、年度、分支與申請／受益角色，再找本方案的資格及申辦段落。'
    '標題或制度名稱只是對象線索，不單獨證明學位或候選人門檻。'
    '保留原定位、否定、例外及相鄰條文；不得將獎助金級距當成申請資格。'
    '資助、公告、收件與洽詢角色分開，多個窗口並列，不用頁尾總機推定承辦人。'
    '學生、院系、學院、校級、機構及補件時間分開；常態月日不補年度，'
    '購買期、公告日、結果日不當受理起日。只回傳有證據的欄位，無法判讀保留未知。'
)
PLACEHOLDER = '身分條件請至來源定位核對'
INJECTION = re.compile(r'忽略(?:前述|所有)|ignore\s+(?:previous|all)|SYSTEM\s*OVERRIDE',re.I)
PRIVATE = re.compile(r'名冊|名單|姓名|學號|身分證|@|\b0\d[-\s]?\d{6,}')


def compact(value):
    return re.sub(r'\s+','',value)


def safe_units(blocks):
    # Short adjacent PDF lines can form a sentence, but never cross a page,
    # heading, section, table row or another numbered clause.
    for i,block in enumerate(blocks):
        if INJECTION.search(block['text']) or PRIVATE.search(block['text']):continue
        units=[block];text=block['text']
        for other in blocks[i+1:i+3]:
            if (len(compact(text))>=160 or other.get('page')!=block.get('page')
                    or other.get('section_path',[])!=block.get('section_path',[])
                    or block.get('kind') in ('heading','table_cell') or other.get('kind') in ('heading','table_cell')
                    or re.match(r'^(?:第[一二三四五六七八九十]+條|[一二三四五六七八九十]+[、.]|[（(][一二三四五六七八九十]+[)）]|[（(]?\d+[.、)）])',other['text'].strip())
                    or INJECTION.search(other['text']) or PRIVATE.search(other['text'])):break
            if not block.get('page'):break  # HTML semantic paragraphs already joined.
            units.append(other);text+=other['text']
        yield compact(text),units


def degree_terms(text):
    degrees=[]
    if re.search(r'碩士|碩[、及或與]?博',text):degrees.append('master')
    if re.search(r'博士|碩[、及或與]?博',text):degrees.append('phd')
    return degrees


def discover_identity(blocks):
    options=[]
    for text,units in safe_units(blocks):
        if units[0].get('kind')=='heading':continue
        # A student's transcript or a salary table is not an enrollment criterion.
        if re.search(r'成績單|學位證書|每月|每年.{0,8}元|支給|薪資|給付|上限|下限',text):continue
        student=bool(re.search(r'在學.{0,16}(?:學生|研究生)|(?:現正|現)?就讀.{0,36}(?:博士|碩士)|'
            r'(?:博士班|碩士班|碩[、及或與]?博(?:士)?班).{0,10}(?:學生|研究生)|研究生[：:].{0,30}(?:博士|碩士)',text))
        if not student:continue
        if re.search(r'鼓勵|吸引|發揮潛能|目的',text) and not re.search(r'申請資格|凡|應具|須具|現正就讀',text):continue
        positive=[part for part in re.split(r'[，,；;。]',text)
            if not re.search(r'不得|不含|不包括|排除|不適用',part)]
        degrees=degree_terms('；'.join(positive))
        parts=[('碩、博士班學生' if len(degrees)==2 else '博士班學生' if degrees==['phd'] else '碩士班學生' if degrees==['master'] else '在學學生')]
        if '本院' in text:parts.append('本院所屬範圍')
        elif '本校' in text:parts.append('本校學籍範圍')
        elif re.search(r'國內.{0,12}大學',text):parts.append('國內大學學籍範圍')
        if '在學一年以上' in text:parts.append('在學須滿一年')
        if '系所推薦' in text:parts.append('須經系所推薦')
        if re.search(r'不含|不得|排除|非在職',text):parts.append('另有排除條件')
        parts.append('其餘資格、排除與文件要求請核對來源')
        score=3*bool(re.search(r'資格|凡|現正就讀|應具|須具',text))+bool(degrees)
        options.append((score,{'text':'；'.join(parts),'degrees':degrees,'units':units,'kind':'eligibility_clause'}))
    if options:return max(options,key=lambda item:item[0])[1]
    # Useful descriptors do not become strict degree/candidate filter matches.
    for text,units in safe_units(blocks):
        if '博士候選人' in text and re.search(r'培育|獎勵|計畫|博士論文',text):
            fields=[name for name in ('人文','社會科學') if name in text]
            return {'text':'博士候選人相關計畫'+('（'+ '／'.join(fields)+'領域）' if fields else '')+'；完整資格請查要點與各所公告',
                    'degrees':[],'units':units,'kind':'program_descriptor'}
        if '教學助理' in text and re.search(r'制度|辦法|申請',text):
            return {'text':'教學助理相關制度；實際任用身分與資格請查辦法及個別招募',
                    'degrees':[],'units':units,'kind':'program_descriptor'}
        if '研究生獎勵金' in text and re.search(r'制度|辦法|申請|實施',text):
            return {'text':'研究生獎勵金相關制度；獎助與勞僱分流及各系所資格請查原文',
                    'degrees':[],'units':units,'kind':'program_descriptor'}
    return None


def discover_organizations(blocks):
    roles={'receiver':[],'funder':[],'announcer':[]}
    # Role-bearing expressions; never collect every organization mentioned.
    target=r'(?:所屬(?:院系所|系所|學院|學系)|各(?:研究所|系所|學院|單位)|申請機構|本(?:會|院|校|局|中心)|[\u4e00-\u9fff]{2,16}(?:委員會|研究院|大學|基金會|學院|處|中心|組|局))'
    patterns={
        'receiver':[r'(?:送交|送至|送達|向|洽)(?P<name>'+target+r')(?:提出|申請|辦理|彙|各|[（(，,。；;：:]|$)',
                    r'(?:收件單位|受理單位|承辦單位)[：:](?P<name>'+target+r')'],
        'funder':[r'(?:經費由|經費來源[：:]|補助單位[：:])(?P<name>'+target+r')',
                  r'(?P<name>'+target+r')(?:補助|提供經費|編列預算)'],
        'announcer':[r'(?:主辦單位|公告單位)[：:](?P<name>'+target+r')']}
    for text,units in safe_units(blocks):
        if units[0].get('kind')=='heading':continue
        for role,expressions in patterns.items():
            for expression in expressions:
                for match in re.finditer(expression,text):
                    name=re.sub(r'^(?:獲|由|經|請|並|得|可|予以)+','',match['name'])
                    if re.search(r'不(?:向|由|送)|無須|不得',text[max(0,match.start()-4):match.end()]):continue
                    if name not in [claim['value'] for claim in roles[role]]:
                        roles[role].append({'value':name,'units':units})
    return {role:claims for role,claims in roles.items() if claims}


def recurring_time(text):
    """Preserve a recurring rule, never assign the current year."""
    if not re.search(r'申請|受理|截止|彙送|送件',text) or not re.search(r'每年|每學期|各所.*截止|截止.*洽',text):return None
    if re.search(r'核定|出國|購買|訂閱|結果|發放|報到',text):return None
    months=re.findall(r'([一二三四五六七八九十\d]{1,3})月([一二三四五六七八九十廿卅\d]{1,3})日',text)
    if not months:return None
    actor='institution' if re.search(r'申請機構|學校彙|備函',text) else 'college' if '學院彙' in text else 'student' if re.search(r'學生|申請人|申請者',text) else 'unit'
    rule='；'.join(month+'月'+day+'日' for month,day in months)
    return {'actor':actor,'action':'依常態規則辦理；當期年度與收件窗口另查',
            'deadline':{'kind':'relative','value':None,'timezone':'Asia/Taipei',
                        'note':'來源常態月日：'+rule+'；不換算為當期日期，起訖與程序依原文確認'}}


def time_actor(text):
    if re.search(r'申請機構|學校彙|備函',text):return 'institution'
    if re.search(r'各學院|學院彙',text):return 'college'
    if re.search(r'學生|申請人|申請者',text):return 'student'
    return 'unit'
