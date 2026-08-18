with open(r'd:\kaifa\wheat-fe\frontend\index.html', encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        if "modal.type === 'qr'" in line:
            print(f'{i}: {line.rstrip()[:180]}')
        elif "modal.type === 'op'" in line:
            print(f'{i}: {line.rstrip()[:180]}')
        elif "v-if=\"modal.show\"" in line:
            print(f'{i}: {line.rstrip()[:180]}')
