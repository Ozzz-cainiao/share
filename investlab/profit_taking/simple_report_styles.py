CSS = """
:root{--paper:#F5F7FB;--card:#FFFFFF;--surface-subtle:#EEF2F8;--ink:#26304A;--muted:#68758B;--line:#DCE2ED;--brand:#405477;--positive:#1A7A3A;--negative:#B53636;--warning-bg:#FFF8DC;--warning-line:#DFC578;--space-1:4px;--space-2:8px;--space-3:12px;--space-4:16px;--space-6:24px;--space-8:32px;--space-10:40px;--space-12:48px;--space-16:64px;--space-20:80px}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;font-size:15px;line-height:1.7}
.shell{max-width:960px;margin:0 auto;padding:44px 28px 60px}
.hero{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(280px,.6fr);gap:var(--space-16);padding:var(--space-20) 0 var(--space-16);border-bottom:1px solid var(--line)}
.overline{margin:0 0 var(--space-3);font-size:11px;font-weight:600;letter-spacing:.08em;color:var(--brand)}
h1{max-width:760px;margin:0;font:600 34px/1.2 Georgia,"Songti SC",serif}
h2{margin:0;font-size:22px;line-height:1.35}
.lead{max-width:680px;margin:var(--space-6) 0 0;color:var(--muted);font-size:15px;line-height:1.7}
.headline-result{align-self:end;margin:0;padding:var(--space-6);background:var(--card);border:1px solid var(--line);box-shadow:0 4px 18px rgba(35,45,75,.04)}
.headline-result div+div{margin-top:var(--space-6);padding-top:var(--space-4);border-top:1px solid var(--line)}
dt{font-size:14px;color:var(--muted)}
.headline-result dt{color:var(--muted)}
dd{margin:var(--space-2) 0 0;font-variant-numeric:tabular-nums;font-weight:650}
.headline-result dd{font-size:30px}
.headline-result .profit dd{color:var(--positive)}
section{padding:var(--space-16) 0;border-bottom:1px solid var(--line)}
.section-heading{display:grid;grid-template-columns:180px 1fr;gap:var(--space-6);margin-bottom:var(--space-10)}
.result-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin:0;border-top:1px solid var(--line)}
.result-grid>div{padding:var(--space-6) var(--space-4);border-bottom:1px solid var(--line);border-left:1px solid var(--line)}
.result-grid>div:nth-child(4n+1){padding-left:0;border-left:0}
.result-grid dd{font-size:24px}
.result-grid p{margin:var(--space-1) 0 0;color:var(--muted);font-size:14px}
.chart{margin:0;padding:var(--space-6);background:var(--card);border:1px solid var(--line);box-shadow:0 4px 18px rgba(35,45,75,.04)}
.chart svg{display:block;width:100%;height:auto}
.axis{stroke:var(--line);stroke-width:1}
.line{fill:none;stroke-width:3;vector-effect:non-scaling-stroke}
.assets{stroke:var(--ink)}.invested{stroke:var(--muted);stroke-dasharray:8 8}.reserve{stroke:var(--positive)}
.chart figcaption{display:flex;flex-wrap:wrap;gap:var(--space-6);margin-top:var(--space-4);font-size:14px}
.key::before{display:inline-block;width:20px;height:3px;margin-right:var(--space-2);vertical-align:middle;background:var(--ink);content:""}
.invested-key::before{background:var(--muted)}.reserve-key::before{background:var(--positive)}
.table-wrap{overflow-x:auto;border:1px solid var(--line);background:var(--card);box-shadow:0 4px 20px rgba(35,45,75,.06)}
.table-wrap:focus-visible{outline:3px solid var(--brand);outline-offset:2px}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
caption{padding:var(--space-4);text-align:left;font-weight:650}
th,td{padding:12px 16px;border-top:1px solid var(--line);text-align:right;white-space:nowrap}
th:nth-child(2),td:nth-child(2){text-align:left}
th{font-size:13px;letter-spacing:.05em;color:var(--muted)}
tbody tr:hover{background:var(--surface-subtle)}
.empty{margin:0;padding:var(--space-8);border:1px solid var(--line);background:var(--card)}
.method{display:grid;grid-template-columns:minmax(180px,.45fr) minmax(0,1.55fr);gap:var(--space-12)}.method>*{min-width:0}
.method-copy p{margin:0 0 var(--space-4)}.source{overflow-wrap:anywhere;color:var(--muted);font-size:14px}.nowrap{white-space:nowrap}
footer{padding:var(--space-8) 0;color:var(--muted);font-size:13px}
@media(max-width:767px){.shell{padding:24px 14px 40px}.hero{grid-template-columns:1fr;gap:var(--space-10);padding:var(--space-12) 0}.section-heading,.method{grid-template-columns:1fr;gap:var(--space-3)}.headline-result{padding:var(--space-6)}section{padding:var(--space-12) 0}.chart{padding:var(--space-3)}h1{font-size:29px}}
@media(max-width:679px){.result-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.result-grid>div:nth-child(odd){padding-left:0;border-left:0}.result-grid>div:nth-child(even){padding-right:0;border-left:1px solid var(--line)}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
"""
