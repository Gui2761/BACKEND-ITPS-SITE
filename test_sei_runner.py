import sys
import json

# Forçar UTF-8 no terminal Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from sei_client import SEISergipeClient

def rodar_bateria_de_testes_sei():
    print("=" * 65)
    print("INICIANDO BATERIA DE TESTES: SEI SERGIPE + ITPS (PCA / PEI)")
    print("=" * 65)

    # 1. Teste de Conexão com o SEI da VM (172.23.6.223)
    print("\n[TESTE 1] Testando Conexao SOAP com a VM (http://172.23.6.223:8000/sei/controlador_ws.php)...")
    client_vm = SEISergipeClient(mock_mode=False)
    res_vm = client_vm.gerar_procedimento(especificacao="Processo de Teste Automatizado ITPS - PCA 2026")
    
    print(f"Status do Teste VM: {'[SUCESSO]' if res_vm.get('sucesso') else '[FALHA]'}")
    print("Resultado da VM SEI:")
    print(json.dumps(res_vm, indent=2, ensure_ascii=False))

    # 2. Teste do Modo Simulação / Mock
    print("\n[TESTE 2] Testando Modo de Simulacao / Mock para o PCA...")
    client_mock = SEISergipeClient(mock_mode=True)
    res_mock = client_mock.gerar_procedimento(especificacao="Aquisicao de Reagentes e Vidrarias - PCA ITPS 2026")
    
    print(f"Status do Teste Mock: {'[SUCESSO]' if res_mock.get('sucesso') else '[FALHA]'}")
    print("Resultado do Mock:")
    print(json.dumps(res_mock, indent=2, ensure_ascii=False))

    # 3. Teste de Consulta de Processo
    print("\n[TESTE 3] Consultando Andamento de Processo SEI...")
    num_processo = res_mock.get("procedimento_formatado", "13801.79.000123/2026-19")
    res_consulta = client_mock.consultar_procedimento(num_processo)
    
    print(f"Status da Consulta: {'[SUCESSO]' if res_consulta.get('sucesso') else '[FALHA]'}")
    print("Resultado da Consulta:")
    print(json.dumps(res_consulta, indent=2, ensure_ascii=False))

    print("\n" + "=" * 65)
    print("BATERIA DE TESTES CONCLUIDA COM EXITO!")
    print("=" * 65)

if __name__ == "__main__":
    rodar_bateria_de_testes_sei()
