# fccr-scraping

Monitor de publicações do site da Fundação Cultural Cassiano Ricardo (São José dos Campos).

A FCCR não publica RSS, sitemap ou API. Este projeto faz scraping da listagem paginada
de notícias (e de seções hierárquicas como editais, projetos, espaços e mídia), persiste
um índice das publicações já vistas e expõe novidades via:

- **Feed RSS** em `public/feed.xml` (publicado por GitHub Pages).
- **Discord webhook** disparado a cada execução com itens novos.

## Estrutura

```
src/                código do scraper
tests/fixtures/     HTML congelado para testar parsers
data/index.json     índice persistido das publicações já vistas
public/feed.xml     feed RSS regenerado a cada execução
.github/workflows/  GitHub Actions (cron)
```

## Uso local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m src.main           # roda o scraper
pytest                       # roda os testes
```

## Fonte canônica das publicações

`https://fccr.sp.gov.br/fccr/home/noticias?secao_id=75&pagina_atual_lista_noticias=N`
(50 páginas, ~30 itens cada, datas DD/MM/AAAA visíveis).
