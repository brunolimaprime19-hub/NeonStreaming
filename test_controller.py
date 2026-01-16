#!/usr/bin/env python3
"""
Script de teste para verificar inputs do controle virtual
Testa botões, analógicos e D-Pad
"""
import subprocess
import time
import json
import sys

def test_virtual_controller():
    print("=" * 70)
    print("🎮 TESTE DE INPUTS DO CONTROLE VIRTUAL")
    print("=" * 70)
    
    # Verificar se /dev/uinput está acessível
    print("\n[1/5] Verificando permissões do /dev/uinput...")
    try:
        with open('/dev/uinput', 'rb') as f:
            print("✅ /dev/uinput acessível")
    except PermissionError:
        print("❌ ERRO: Sem permissão para /dev/uinput")
        print("   Execute: sudo chmod +0666 /dev/uinput")
        return False
    except FileNotFoundError:
        print("❌ ERRO: /dev/uinput não encontrado")
        print("   Execute: sudo modprobe uinput")
        return False
    
    # Verificar se o módulo evdev está instalado
    print("\n[2/5] Verificando módulo evdev...")
    try:
        import evdev
        print(f"✅ evdev instalado")
    except ImportError:
        print("❌ ERRO: evdev não instalado")
        print("   Execute: pip3 install evdev")
        return False
    
    # Testar criação do controle virtual
    print("\n[3/5] Testando criação do controle virtual...")
    try:
        from input_manager import InputManager
        mgr = InputManager()
        if mgr.ui is None:
            print("❌ ERRO: Falha ao criar controle virtual")
            return False
        print("✅ Controle virtual 'NeonCloudController' criado")
    except Exception as e:
        print(f"❌ ERRO ao criar InputManager: {e}")
        return False
    
    # Aguardar o sistema reconhecer o dispositivo
    time.sleep(1)
    
    # Verificar se o dispositivo apareceu
    print("\n[4/5] Verificando dispositivos de entrada...")
    try:
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        neon_device = None
        for device in devices:
            if "NeonCloudController" in device.name:
                neon_device = device
                print(f"✅ Dispositivo encontrado: {device.name}")
                print(f"   Path: {device.path}")
                print(f"   Capabilities: {len(device.capabilities())} tipos de evento")
                break
        
        if not neon_device:
            print("⚠️ Dispositivo 'NeonCloudController' não encontrado na lista")
            print("   Dispositivos disponíveis:")
            for dev in devices:
                print(f"   - {dev.name}")
    except Exception as e:
        print(f"⚠️ Erro ao listar dispositivos: {e}")
    
    # Testar inputs
    print("\n[5/5] Testando inputs do controle...")
    print("-" * 70)
    
    test_cases = [
        # Botões
        {"type": "BUTTON", "code": "A", "value": 1, "desc": "Botão A pressionado"},
        {"type": "BUTTON", "code": "A", "value": 0, "desc": "Botão A solto"},
        {"type": "BUTTON", "code": "B", "value": 1, "desc": "Botão B pressionado"},
        {"type": "BUTTON", "code": "B", "value": 0, "desc": "Botão B solto"},
        {"type": "BUTTON", "code": "X", "value": 1, "desc": "Botão X pressionado"},
        {"type": "BUTTON", "code": "Y", "value": 1, "desc": "Botão Y pressionado"},
        {"type": "BUTTON", "code": "START", "value": 1, "desc": "Botão START pressionado"},
        {"type": "BUTTON", "code": "SELECT", "value": 1, "desc": "Botão SELECT pressionado"},
        
        # D-Pad
        {"type": "BUTTON", "code": "DPAD_UP", "value": 1, "desc": "D-Pad UP"},
        {"type": "BUTTON", "code": "DPAD_UP", "value": 0, "desc": "D-Pad UP solto"},
        {"type": "BUTTON", "code": "DPAD_DOWN", "value": 1, "desc": "D-Pad DOWN"},
        {"type": "BUTTON", "code": "DPAD_LEFT", "value": 1, "desc": "D-Pad LEFT"},
        {"type": "BUTTON", "code": "DPAD_RIGHT", "value": 1, "desc": "D-Pad RIGHT"},
        
        # Analógicos
        {"type": "AXIS", "code": "LEFT_X", "value": 16000, "desc": "Analógico esquerdo → direita"},
        {"type": "AXIS", "code": "LEFT_X", "value": -16000, "desc": "Analógico esquerdo → esquerda"},
        {"type": "AXIS", "code": "LEFT_X", "value": 0, "desc": "Analógico esquerdo → centro"},
        {"type": "AXIS", "code": "LEFT_Y", "value": 16000, "desc": "Analógico esquerdo ↓ baixo"},
        {"type": "AXIS", "code": "LEFT_Y", "value": -16000, "desc": "Analógico esquerdo ↑ cima"},
        {"type": "AXIS", "code": "RIGHT_X", "value": 16000, "desc": "Analógico direito → direita"},
        {"type": "AXIS", "code": "RIGHT_Y", "value": 16000, "desc": "Analógico direito ↓ baixo"},
        
        # Gatilhos
        {"type": "BUTTON", "code": "LB", "value": 1, "desc": "Bumper esquerdo (LB)"},
        {"type": "BUTTON", "code": "RB", "value": 1, "desc": "Bumper direito (RB)"},
        {"type": "BUTTON", "code": "LT", "value": 1, "desc": "Gatilho esquerdo (LT)"},
        {"type": "BUTTON", "code": "RT", "value": 1, "desc": "Gatilho direito (RT)"},
    ]
    
    success_count = 0
    fail_count = 0
    
    for i, test in enumerate(test_cases, 1):
        try:
            mgr.handle_input(test)
            print(f"  [{i:2d}/{len(test_cases)}] ✅ {test['desc']}")
            success_count += 1
            time.sleep(0.05)  # Pequeno delay entre inputs
        except Exception as e:
            print(f"  [{i:2d}/{len(test_cases)}] ❌ {test['desc']} - Erro: {e}")
            fail_count += 1
    
    # Limpar
    mgr.close()
    
    # Resumo
    print("-" * 70)
    print(f"\n📊 RESUMO DOS TESTES:")
    print(f"   ✅ Sucessos: {success_count}/{len(test_cases)}")
    print(f"   ❌ Falhas:   {fail_count}/{len(test_cases)}")
    
    if fail_count == 0:
        print("\n" + "=" * 70)
        print("🎉 TODOS OS INPUTS FUNCIONARAM PERFEITAMENTE!")
        print("=" * 70)
        return True
    else:
        print("\n⚠️ Alguns inputs falharam")
        return False

def test_with_evtest():
    """Teste adicional usando evtest para monitorar eventos"""
    print("\n" + "=" * 70)
    print("🔍 TESTE ADICIONAL: Monitoramento de Eventos")
    print("=" * 70)
    print("\nPara monitorar eventos em tempo real, execute em outro terminal:")
    print("   sudo evtest")
    print("\nE selecione o dispositivo 'NeonCloudController'")
    print("Você verá todos os eventos de botões e analógicos em tempo real!")

if __name__ == "__main__":
    print("\n🎮 INICIANDO TESTES DO CONTROLE VIRTUAL\n")
    
    result = test_virtual_controller()
    test_with_evtest()
    
    if result:
        print("\n✅ Sistema de controle está funcionando corretamente!")
        print("   Você pode usar um gamepad físico ou virtual no navegador")
        print("   e os inputs serão transmitidos para o servidor.\n")
        sys.exit(0)
    else:
        print("\n❌ Alguns problemas foram encontrados.")
        print("   Verifique os erros acima e corrija antes de usar.\n")
        sys.exit(1)
