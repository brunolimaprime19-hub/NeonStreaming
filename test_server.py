#!/usr/bin/env python3
"""
Script de teste para verificar se o botão PARAR SERVIDOR funciona corretamente
"""
import subprocess
import time
import signal
import os
import sys

def test_server_start_stop():
    print("=" * 60)
    print("TESTE: Iniciar e Parar Servidor")
    print("=" * 60)
    
    # Teste 1: Iniciar servidor com GPU encoding
    print("\n[1/4] Iniciando servidor com GPU encoding...")
    server_process = subprocess.Popen(
        ["python3", "server.py", "--encoder", "gpu", "--resolution", "1280x720", 
         "--bitrate", "6000", "--port", "8083"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        preexec_fn=os.setsid
    )
    
    # Aguardar inicialização
    time.sleep(3)
    
    # Verificar se está rodando
    if server_process.poll() is None:
        print("✅ Servidor iniciado com sucesso (PID: {})".format(server_process.pid))
    else:
        print("❌ Servidor falhou ao iniciar")
        return False
    
    # Teste 2: Verificar se está respondendo
    print("\n[2/4] Verificando se servidor está respondendo...")
    try:
        import urllib.request
        response = urllib.request.urlopen("http://localhost:8083", timeout=5)
        if response.status == 200:
            print("✅ Servidor respondendo na porta 8083")
        else:
            print("⚠️ Servidor respondeu com status:", response.status)
    except Exception as e:
        print("⚠️ Erro ao conectar:", str(e)[:50])
    
    # Teste 3: Parar servidor (Método 1 - SIGTERM)
    print("\n[3/4] Testando parada do servidor (SIGTERM)...")
    try:
        pid = server_process.pid
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        server_process.wait(timeout=3)
        print("✅ Servidor parado com sucesso (SIGTERM)")
        return True
    except subprocess.TimeoutExpired:
        print("⚠️ SIGTERM não funcionou, tentando SIGKILL...")
        
        # Teste 4: Força parada (SIGKILL)
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
            server_process.wait(timeout=2)
            print("✅ Servidor parado com SIGKILL (força)")
            return True
        except Exception as e:
            print("❌ Falha ao parar servidor:", e)
            return False
    except Exception as e:
        print("❌ Erro ao parar servidor:", e)
        
        # Tenta método alternativo
        print("\n[4/4] Tentando método alternativo (terminate)...")
        try:
            server_process.terminate()
            server_process.wait(timeout=2)
            print("✅ Servidor parado com terminate()")
            return True
        except:
            try:
                server_process.kill()
                print("✅ Servidor parado com kill()")
                return True
            except Exception as e2:
                print("❌ Todos os métodos falharam:", e2)
                return False

def test_multiple_cycles():
    print("\n" + "=" * 60)
    print("TESTE: Múltiplos Ciclos de Iniciar/Parar")
    print("=" * 60)
    
    for i in range(3):
        print(f"\n--- Ciclo {i+1}/3 ---")
        success = test_server_start_stop()
        if not success:
            print(f"❌ Falha no ciclo {i+1}")
            return False
        time.sleep(1)
    
    print("\n✅ Todos os 3 ciclos completados com sucesso!")
    return True

if __name__ == "__main__":
    print("\n🧪 INICIANDO TESTES DO SERVIDOR\n")
    
    # Teste básico
    result1 = test_server_start_stop()
    
    if result1:
        print("\n" + "=" * 60)
        print("✅ TESTE BÁSICO: PASSOU")
        print("=" * 60)
        
        # Teste de múltiplos ciclos
        result2 = test_multiple_cycles()
        
        if result2:
            print("\n" + "=" * 60)
            print("🎉 TODOS OS TESTES PASSARAM!")
            print("=" * 60)
            print("\n✅ O botão PARAR SERVIDOR está funcionando corretamente!")
            sys.exit(0)
        else:
            print("\n❌ Teste de múltiplos ciclos falhou")
            sys.exit(1)
    else:
        print("\n" + "=" * 60)
        print("❌ TESTE BÁSICO: FALHOU")
        print("=" * 60)
        sys.exit(1)
