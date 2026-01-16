# Como Gerar o Executável (.exe) para Windows

Como o ambiente atual é Linux, não é possível gerar o arquivo `.exe` diretamente. Você tem duas opções simples para conseguir o seu executável:

### Opção 1: Usando o GitHub (Automático e Profissional)
Eu já configurei o **GitHub Actions** para você. Sempre que você subir o código para o GitHub, ele vai gerar o executável sozinho:
1. Crie um repositório no GitHub.
2. Suba os arquivos do projeto.
3. Vá na aba **"Actions"** no seu repositório.
4. Lá você verá o build acontecendo. Quando terminar, você poderá baixar o `NeonStreamServer-windows` nos artefatos.

### Opção 2: Rodando em qualquer PC com Windows
Se você tiver acesso a um Windows:
1. Instale o Python (3.11 ou 3.12 recomendado).
2. Abra a pasta do projeto no terminal (CMD ou PowerShell).
3. Rode o comando:
   ```bash
   python build.py
   ```
4. O executável aparecerá na pasta `dist/`.

### Por que não posso fazer agora?
O `PyInstaller` (ferramenta de empacotamento) precisa "colar" as bibliotecas do sistema operacional no arquivo. Para criar um arquivo do Windows, ele precisa estar rodando dentro do Windows para pegar as DLLs e componentes corretos.
