"""Teste de conexao do Userbot."""
import asyncio
from src.userbot import userbot
from src.services.parser import ResponseParser

async def main():
    print("Conectando Userbot...")
    
    if await userbot.start():
        print("Conectado!\n")
        
        # Teste POSTE
        print("=" * 50)
        print("Testando /pte 2082518 (POSTE)...")
        print("=" * 50)
        response = await userbot.query_poste("2082518")
        
        if response:
            print(f"Resposta ({len(response)} chars):\n")
            print(response)
            print("-" * 50)
            
            parsed = ResponseParser.parse(response)
            if parsed:
                print(f"\n Parse OK: {parsed.tipo.value}")
                print(f"   Codigo: {parsed.codigo}")
                if parsed.coordenadas:
                    print(f"   Coordenadas: {parsed.coordenadas.dms}")
                    print(f"   Google Maps: {parsed.coordenadas.google_maps_url}")
            else:
                print("\n Parser nao reconheceu o formato")
        else:
            print("Sem resposta (timeout)")
        
        await userbot.stop()
    else:
        print("Falha ao conectar")

if __name__ == "__main__":
    asyncio.run(main())
