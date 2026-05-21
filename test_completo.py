"""Teste completo: POSTE e EQUIPAMENTO."""
import asyncio
from src.userbot import userbot
from src.services.parser import ResponseParser

parser = ResponseParser()

async def main():
    print("Conectando Userbot...")
    
    if await userbot.start():
        print("Conectado!\n")
        
        # Teste POSTE
        print("=" * 50)
        print("1. Testando POSTE 2082518")
        print("=" * 50)
        
        resp = await userbot.query_poste("2082518")
        if resp:
            print(f"Resposta:\n{resp}\n")
            parsed = parser.parse(resp)
            if parsed:
                print(f"✅ Tipo: {parsed.tipo}")
                print(f"✅ Código: {parsed.codigo}")
                print(f"✅ Coords: {parsed.coordenadas}")
            else:
                print(f"⚠️ Não foi possível parsear (resposta do bot: {resp})")
        
        await asyncio.sleep(1)
        
        # Teste EQUIPAMENTO (código real se tiver, senão testa o fluxo)
        print("\n" + "=" * 50)
        print("2. Testando EQUIPAMENTO IBS3135")
        print("=" * 50)
        
        resp = await userbot.query_equipamento("IBS3135")
        if resp:
            print(f"Resposta:\n{resp}\n")
            parsed = parser.parse(resp)
            if parsed:
                print(f"✅ Tipo: {parsed.tipo}")
                print(f"✅ Código: {parsed.codigo}")
                print(f"✅ Coords: {parsed.coordenadas}")
            else:
                print(f"⚠️ Equipamento não encontrado ou formato não reconhecido")
        
        await userbot.stop()
        print("\n🎉 Todos os testes concluídos!")
    else:
        print("Falha ao conectar")

if __name__ == "__main__":
    asyncio.run(main())
