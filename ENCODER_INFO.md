# Guia de Encoders - Neon Stream

## Opções de Encoder

O Neon Stream agora suporta duas opções de encoding de vídeo:

### 🖥️ CPU Encoding (libx264)
**Codec:** H.264 via libx264  
**Hardware:** Processador (CPU)

**Vantagens:**
- ✅ Compatível com qualquer sistema
- ✅ Maior qualidade de imagem em bitrates baixos
- ✅ Mais estável e confiável

**Desvantagens:**
- ❌ Maior uso de CPU (pode impactar performance do jogo)
- ❌ Maior latência em resoluções altas
- ❌ Pode causar aquecimento do processador

**Recomendado para:**
- Sistemas sem GPU dedicada
- Quando a qualidade é mais importante que performance
- Resoluções até 1280x720

---

### 🎮 GPU Encoding (VAAPI - AMD Vega 11)
**Codec:** H.264 via VAAPI  
**Hardware:** GPU integrada AMD Vega 11

**Vantagens:**
- ✅ Menor uso de CPU (libera processador para o jogo)
- ✅ Menor latência
- ✅ Melhor performance em resoluções altas (1080p+)
- ✅ Menor aquecimento do processador

**Desvantagens:**
- ❌ Requer drivers VAAPI instalados
- ❌ Qualidade ligeiramente inferior em bitrates muito baixos
- ❌ Pode não funcionar em todos os sistemas

**Recomendado para:**
- Streaming em 1080p ou superior
- Quando a performance do jogo é prioridade
- Sistemas com AMD Vega 11 (como o seu)

---

## Como Usar

### Via GUI (server_gui.py)
1. Abra o Server Manager: `python3 server_gui.py`
2. Selecione o encoder no dropdown "Encoder:"
   - **cpu** = Encoding por CPU (libx264)
   - **gpu** = Encoding por GPU (VAAPI)
3. Configure outras opções (resolução, bitrate, porta)
4. Clique em "INICIAR SERVIDOR"

### Via Linha de Comando
```bash
# CPU Encoding
python3 server.py --encoder cpu --resolution 1280x720 --bitrate 5000

# GPU Encoding
python3 server.py --encoder gpu --resolution 1920x1080 --bitrate 8000
```

---

## Requisitos para GPU Encoding

Para usar encoding por GPU (VAAPI) na sua AMD Vega 11, você precisa:

### 1. Drivers Mesa atualizados
```bash
# Verificar versão do Mesa
glxinfo | grep "OpenGL version"

# Deve ser Mesa 20.0 ou superior
```

### 2. VAAPI instalado
```bash
# Instalar pacotes necessários
sudo apt install mesa-va-drivers vainfo

# Verificar se VAAPI está funcionando
vainfo

# Deve mostrar: "VAProfileH264Main" e "VAProfileH264High"
```

### 3. FFmpeg com suporte VAAPI
```bash
# Verificar se FFmpeg tem VAAPI
ffmpeg -hwaccels

# Deve listar "vaapi" na saída
```

---

## Troubleshooting

### GPU Encoding não funciona?

**Erro: "Cannot load libva"**
```bash
sudo apt install libva2 libva-drm2
```

**Erro: "No VA display found"**
```bash
# Verificar se /dev/dri/renderD128 existe
ls -la /dev/dri/

# Se não existir, pode ser renderD129
# Edite server.py linha 110 e mude para renderD129
```

**Erro: "Failed to initialize VAAPI"**
```bash
# Adicione seu usuário ao grupo video
sudo usermod -a -G video $USER

# Faça logout e login novamente
```

### CPU Encoding muito lento?

- Reduza a resolução (use 1280x720 ao invés de 1920x1080)
- Reduza o bitrate (tente 3000-4000 kbps)
- Reduza o FPS (use 30 ao invés de 60)

---

## Comparação de Performance

| Configuração | CPU (Ryzen com Vega 11) | Qualidade | Latência |
|--------------|-------------------------|-----------|----------|
| **CPU 720p 30fps** | ~40-60% | ⭐⭐⭐⭐⭐ | ~50-80ms |
| **CPU 1080p 60fps** | ~80-100% | ⭐⭐⭐⭐⭐ | ~100-150ms |
| **GPU 720p 30fps** | ~10-20% | ⭐⭐⭐⭐ | ~30-50ms |
| **GPU 1080p 60fps** | ~15-30% | ⭐⭐⭐⭐ | ~40-70ms |

**Recomendação:** Use **GPU encoding** para melhor experiência geral!

---

## Configurações Recomendadas

### Para Jogos de Ação/FPS
```
Encoder: GPU
Resolução: 1280x720
Bitrate: 6000 kbps
FPS: 60
```

### Para Jogos Estratégia/RPG
```
Encoder: GPU
Resolução: 1920x1080
Bitrate: 8000 kbps
FPS: 30
```

### Para Conexões Lentas
```
Encoder: CPU
Resolução: 1024x576
Bitrate: 2500 kbps
FPS: 30
```
