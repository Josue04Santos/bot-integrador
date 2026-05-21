"""Teste para descobrir comandos do bot."""
import asyncio
from src.userbot import userbot

async def main():
    print("Conectando Userbot...")
    
    if await userbot.start():
        print("Conectado!\n")
        
        print("=" * 50)
        print("Enviando /Menu para descobrir comandos...")
        print("=" * 50)
        
        # Envia /Menu
        response = await userbot._send_query("/Menu")
        
        if response:
            print(f"\nResposta:\n")
            print(response)
        else:
            print("Sem resposta")
        
        await userbot.stop()
    else:
        print("Falha ao conectar")

if __name__ == "__main__":
    asyncio.run(main())
