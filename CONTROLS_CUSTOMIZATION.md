# 🎮 Sistema de Customização de Controles

## 📋 Visão Geral

O sistema de customização de controles permite que os usuários personalizem completamente a interface de controle virtual do Cloud Gaming Neo. Este sistema oferece:

- **Movimentação de controles** via arrastar e soltar
- **Ajuste de tamanho** (Pequeno, Médio, Grande)
- **Persistência** automática no localStorage
- **Reset** para configurações padrão

## 🚀 Como Usar

### 1. Acessar o Painel de Configuração

Clique no ícone de **engrenagem (⚙️)** no canto superior direito da tela para abrir o painel de customização.

### 2. Ativar o Modo de Edição

No painel de customização:
1. Ative o switch **"Modo Edição"**
2. Um indicador aparecerá na tela: "✏️ Modo de Edição Ativo - Arraste os controles"
3. Os controles ficarão com bordas tracejadas azuis, indicando que podem ser movidos

### 3. Mover os Controles

Com o modo de edição ativo:
- **Toque e arraste** qualquer grupo de controles para reposicioná-lo
- Os grupos movíveis são:
  - Controles esquerdos (Joystick + D-Pad)
  - Controles direitos (Botões ABXY + Joystick)
  - Controles centrais (Botões Start, Select, Home)
  - Gatilhos esquerdos (LT, LB)
  - Gatilhos direitos (RT, RB)

### 4. Ajustar o Tamanho

No painel de customização, escolha um dos tamanhos disponíveis:
- **Pequeno (0.7x)** - Ideal para telas maiores
- **Médio (1.0x)** - Tamanho padrão
- **Grande (1.3x)** - Melhor para dispositivos menores ou usuários com dificuldade de precisão

### 5. Salvar Configurações

As configurações são salvas **automaticamente** quando você:
- Move um controle
- Altera o tamanho
- Desativa o modo de edição

### 6. Restaurar Padrões

Se desejar voltar às configurações originais:
1. Clique no botão **"Restaurar Padrões"**
2. Confirme a ação
3. Todos os controles voltarão para suas posições e tamanhos originais

## 💾 Persistência de Dados

As configurações são armazenadas no **localStorage** do navegador com a chave `controlSettings`:

```json
{
  "scale": 1.0,
  "positions": {
    "left-controls": { "left": "0px", "top": "0px" },
    "right-controls": { "left": "50px", "top": "-20px" },
    "center-controls": { "left": "0px", "top": "0px" },
    "shoulder-left": { "left": "0px", "top": "0px" },
    "shoulder-right": { "left": "0px", "top": "0px" }
  }
}
```

### Limpando Configurações

Para limpar manualmente as configurações salvas, execute no console do navegador:

```javascript
localStorage.removeItem('controlSettings');
location.reload();
```

## 🎨 Recursos Visuais

### Modo de Edição
- **Bordas tracejadas azuis** ao redor dos controles movíveis
- **Cursor de movimento** quando passa sobre os controles
- **Indicador visual** no topo da tela
- **Opacidade reduzida** ao arrastar

### Painel de Customização
- **Design glassmorphic** moderno
- **Toggle switch** animado para modo de edição
- **Botões de tamanho** com feedback visual
- **Dica informativa** sobre salvamento automático

## 🔧 Detalhes Técnicos

### Arquivos Modificados

1. **index.html**
   - Adicionado botão de configurações no header
   - Adicionado painel de customização overlay

2. **index.css**
   - Estilos para o painel de customização
   - Estilos para modo de edição
   - Estilos para indicadores visuais

3. **client.js**
   - Classe `ControlCustomizer` completa
   - Gerenciamento de drag-and-drop
   - Persistência no localStorage
   - Controle de escala

### Classe ControlCustomizer

Principais métodos:

- `init()` - Inicializa o sistema e carrega configurações
- `toggleEditMode(enabled)` - Ativa/desativa modo de edição
- `enableDragging()` - Adiciona handlers de arrastar
- `disableDragging()` - Remove handlers de arrastar
- `setScale(scale)` - Ajusta o tamanho dos controles
- `applyScale()` - Aplica a escala aos elementos
- `applyPositions()` - Aplica as posições salvas
- `resetControls()` - Restaura configurações padrão
- `saveSettings()` - Salva no localStorage
- `loadSettings()` - Carrega do localStorage

## 📱 Compatibilidade

- ✅ **Touch devices** (smartphones, tablets)
- ✅ **Desktop browsers** (mouse)
- ✅ **Pointer API** para máxima compatibilidade
- ✅ **LocalStorage** para todos os navegadores modernos

## 🎯 Casos de Uso

### Para Jogadores Casuais
- Usar configurações padrão (Médio)
- Mover controles apenas se necessário

### Para Jogadores Competitivos
- Reduzir tamanho para maximizar área de visão
- Posicionar controles em locais ergonômicos específicos

### Para Dispositivos Pequenos
- Aumentar tamanho para melhor precisão
- Reposicionar para evitar obstruir informações importantes

### Para Streamers
- Posicionar controles para não cobrir elementos importantes do jogo
- Ajustar de acordo com o layout do stream

## 🐛 Troubleshooting

### Os controles não estão se movendo
- Verifique se o modo de edição está ativado
- Certifique-se de não estar tocando diretamente em um botão

### As configurações não estão sendo salvas
- Verifique se o localStorage está habilitado no navegador
- Limpe o cache do navegador e tente novamente

### Os controles ficaram fora da tela
- Use o botão "Restaurar Padrões" no painel de configuração
- Ou limpe o localStorage manualmente

## 🚀 Melhorias Futuras (Possíveis)

- [ ] Presets de configuração (Mobile, Tablet, Desktop)
- [ ] Importar/Exportar configurações
- [ ] Opacidade ajustável para controles
- [ ] Temas de cores personalizados
- [ ] Controles individuais de tamanho por elemento
- [ ] Rotação de controles
- [ ] Grades de alinhamento visual
- [ ] Desfazer/Refazer movimentações

---

**Desenvolvido para Cloud Gaming Neo** 🎮
