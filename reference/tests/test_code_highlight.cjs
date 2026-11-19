// 색을 입힌 HTML을 다시 텍스트로 읽어도 원문·줄바꿈이 그대로여야 합니다.
const assert=require('node:assert/strict');
require('../../static/js/code-highlight.js');
const decode=html=>html.replace(/<span class="syntax-[a-z]+">|<\/span>/g,'').replaceAll('&quot;','"').replaceAll('&gt;','>').replaceAll('&lt;','<').replaceAll('&amp;','&');
const cases=[
  ['sample.sql',"-- 한글 주석\nSELECT CASE_ID\n     , 'BUY & SELL' SIGNAL\n  FROM T\n WHERE N = :number\n   AND V < 20\n;"],
  ['sample.sql',"BEGIN\n  p_sql := q'~SELECT 'BUY'\n  FROM T~';\n  -- 따옴표 ' 그대로\nEND;"],
  ['sample.py','# Python 주석\ndef sample(value=None):\n    """여러 줄\n설명"""\n    return "<img src=x onerror=alert(1)>"'],
  ['sample.html','<!-- 주석 -->\n<div title="값">내용 &amp; <script>alert(1)</script></div>'],
  ['sample.js','// 실행하지 않는 코드\nconst value = `문자열`;\n/* 여러\n줄 주석 */'],
  ['sample.json','{"value":"<svg onload=alert(1)>","number":12.34,"null":null}'],
  ['sample.sql',"SELECT '<script>alert(1)</script>' FROM DUAL;\n-- <img src=x onerror=alert(1)>\n"]
];
for(const [path,source] of cases){
  const html=CodeHighlight.html(source,path);
  assert.equal(decode(html),source,path+' 원문 보존');
  assert.ok(!/<(?:img|script|svg|div)\b/i.test(html),'입력 태그는 실행 불가');
  for(const line of html.split('\n'))assert.equal((line.match(/<span /g)||[]).length,(line.match(/<\/span>/g)||[]).length,'줄 번호 표시용 span 균형');
}
const sql=CodeHighlight.html(cases[0][1],'test.sql');
for(const type of ['comment','keyword','string','number','bind'])assert.ok(sql.includes('syntax-'+type),type);
console.log(JSON.stringify({ok:true,cases:cases.length,original_text_preserved:true,input_html_escaped:true,balanced_lines:true}));
