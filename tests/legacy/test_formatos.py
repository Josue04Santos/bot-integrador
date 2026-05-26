"""Teste de diferentes formatos de comando."""
import asyncio
from src.userbot import userbot

async def main():
    print("Conectando Userbot...")
    
    if await userbot.start():
        print("Conectado!\n")
        
        codigo = "2082518"
        
        # Lista de formatos para testar
        formatos = [
            f"/PTE{codigo}",        # Sem espaço
            f"/PTE_{codigo}",       # Com underscore
            f"/PTE\n{codigo}",      # Quebra de linha
            f"/PTE",                # Só o comando (ver se pede o código)
        ]
        
        for fmt in formatos:
            print("=" * 50)
            print(f"Testando: {repr(fmt)}")
            print("=" * 50)
            
            response = await userbot._send_query(fmt)
            
            if response:
                print(f"Resposta:\n{response[:200]}")
            else:
                print("Sem resposta ou timeout")
            
            print()
            await asyncio.sleep(1)  # Pequena pausa entre testes
        
        await userbot.stop()
    else:
        print("Falha ao conectar")

if __name__ == "__main__":
    asyncio.run(main())
