"""
Regenera as seções "Relacionadas" de todas as notas do cofre.

Útil depois de mudar o corte de similaridade (RELATED_MAX_DISTANCE em
src/ingest.py): apaga os links antigos e recria com o critério atual.
Só mexe na seção de links — o texto que você escreveu fica intacto.

Rode da raiz do projeto:
    python scripts/relink.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingest import rebuild_links


def main():
    print("Regenerando os links entre notas...\n")
    com_links = rebuild_links()
    print(f"\nPronto. {com_links} notas ficaram com pelo menos uma relacionada.")


if __name__ == "__main__":
    main()
