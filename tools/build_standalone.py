import os
import re

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
html = open(f'{base}/index.html', encoding='utf-8').read()
css = open(f'{base}/css/styles.css', encoding='utf-8').read()

def wrap_module(path, name, exports):
    src = open(path, encoding='utf-8').read()
    # drop import statements (single or multi-line)
    src = re.sub(r"^import[\s\S]*?from '[^']+';\s*$", '', src, flags=re.M)
    # turn exports into plain declarations
    src = re.sub(r'^export ', '', src, flags=re.M)
    return (f"const {name} = (() => {{\n{src}\n"
            f"return {{ {', '.join(exports)} }};\n}})();\n")

i18n = wrap_module(f'{base}/js/i18n.js', 'I18N',
                   ['t', 'getLang', 'setLang', 'applyStatic'])
data = wrap_module(f'{base}/js/data.js', 'DATA',
                   ['STORAGE_KEY', 'PREFS_KEY', 'EXPIRY_MS', 'SAMPLE_FORMS', 'toAscii',
                    'toDev', 'labelFor', 'fieldPrefill', 'displayValue', 'normalize',
                    'parseText', 'maskPII', 'buildPrefillUrl'])
speech = wrap_module(f'{base}/js/speech.js', 'SPEECH',
                     ['speechInputSupported', 'speechOutputSupported', 'listen',
                      'stopListening', 'speak'])

api = wrap_module(f'{base}/js/api.js', 'API',
                  ['API_BASE', 'SERVER_VALIDATION', 'serverOnline', 'serverValidate',
                   'serverParseText', 'serverExtractText', 'serverParseUrl', 'getAuthToken', 'clearAuthToken',
                   'authRequest', 'authLogin', 'authRegister', 'authGetProfile', 'authUpdateProfile', 'authLogout'])

app_src = open(f'{base}/js/app.js', encoding='utf-8').read()
app_src = re.sub(r"^import[\s\S]*?from '[^']+';\s*$", '', app_src, flags=re.M)
app_head = (
    "const { t, getLang, setLang, applyStatic } = I18N;\n"
    "const { SAMPLE_FORMS, parseText, normalize, labelFor, displayValue, fieldPrefill,\n"
    "  EXPIRY_MS, STORAGE_KEY, PREFS_KEY, buildPrefillUrl } = DATA;\n"
    "const { listen, stopListening, speak, speechInputSupported } = SPEECH;\n"
    "const { serverOnline, serverValidate, serverParseText, serverExtractText, serverParseUrl, authLogin, authRegister, authGetProfile, authUpdateProfile, authLogout, getAuthToken, clearAuthToken } = API;\n"
)
script = i18n + data + speech + api + app_head + app_src

# inline the stylesheet, remove the CSP (it blocks file:// pages) and the module script
html = html.replace('<link rel="stylesheet" href="css/styles.css">', f'<style>\n{css}\n</style>')
html = re.sub(r'\s*<meta http-equiv="Content-Security-Policy"[^>]*>', '', html)
html = html.replace('<script type="module" src="js/app.js"></script>',
                    f'<script>\n{script}\n</script>')

out = f'{base}/awaazform-standalone.html'
open(out, 'w', encoding='utf-8').write(html)
print('written', out, len(html), 'bytes')
