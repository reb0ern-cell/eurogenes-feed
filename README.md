# Comentarios completos do Eurogenes para o NewsBlur

O Blogger corta o texto de todos os comentarios no feed RSS/Atom/JSON aos ~400
caracteres. O texto completo existe no HTML do post, 200 comentarios por pagina
(`?commentPage=N`). Este script monta um feed Atom novo, com o texto inteiro,
dos comentarios mais recentes de todos os posts.

`feed.xml` e gerado no GitHub Actions 3 vezes por dia (de 8 em 8 horas (00:17, 08:17 e 16:17 UTC)) e publicado no GitHub
Pages. No NewsBlur (Android ou web) subscreves esse URL e lês tudo la dentro.

## Publicar

1. Cria um repositorio publico no GitHub, por exemplo `eurogenes-feed`, e faz
   push desta pasta:

   ```bash
   git remote add origin git@github.com:UTILIZADOR/eurogenes-feed.git
   git push -u origin main
   ```

2. No GitHub: **Settings → Pages → Source: Deploy from a branch**, branch
   `main`, pasta `/ (root)`. Guarda.

3. No GitHub: **Actions → feed → Run workflow** uma vez (o primeiro build do
   Pages demora um minuto).

4. O feed fica em:

   ```
   https://UTILIZADOR.github.io/eurogenes-feed/feed.xml
   ```

5. No NewsBlur: **Add Site** e cola esse URL. Podes cancelar a subscricao do
   feed oficial truncado.

## Como funciona

- Sonda o feed de comentarios do blog com 1 item. Se o comentario mais recente
  ja esta no `feed.xml` publicado, termina logo: **1 pedido, ~4 KB**.
- Se ha novidades, le os 100 mais recentes, agrupa por post e vai buscar so as
  paginas necessarias do HTML do post (`?commentPage=N`) para o texto completo.
- Aproveita os comentarios ja no `feed.xml` (`--merge-from`), por isso uma
  execucao com comentarios novos custa ~4 pedidos / ~360 KB.
- Gera um Atom com `<id>` estavel (`comment-<id>`), por isso reescrever o feed
  inteiro nao duplica nada no leitor.
- O `<updated>` do feed e a data do comentario mais recente, nao a hora do
  build: se nao ha comentarios novos, o ficheiro sai igual e o workflow nao faz
  commit.

Carga no Blogger: 3 execucoes/dia. Uma execucao sem novidades custa 1 pedido de
~4 KB; uma com comentarios novos custa ~4 pedidos e ~300 KB.

## Uso local

```bash
python3 blogger_comments.py URL                          # ultimos 10, completos
python3 blogger_comments.py URL -n 30                    # ultimos 30
python3 blogger_comments.py URL --id 4482474905892692466 # um comentario (id do #c<id> do RSS)
python3 blogger_comments.py URL --page 3                 # uma pagina (200)
python3 blogger_comments.py https://eurogenes.blogspot.com --blog -n 300 --feed > feed.xml
python3 blogger_comments.py https://eurogenes.blogspot.com --blog -n 300 --feed --merge-from feed.xml --verbose
```

So precisa de Python 3 (biblioteca standard, sem dependencias).

## Notas

- O cron do GitHub nao e pontual: pode atrasar 10-20 min e, em repos recentes,
  as vezes salta uma execucao. Com 3 por dia nao ha problema; os comentarios
  nao se perdem, entram na execucao seguinte.
- Workflows agendados sao desactivados ao fim de 60 dias sem actividade no
  repositorio. Como o proprio workflow faz commit quando ha comentarios novos,
  isso normalmente nao acontece; se o blog ficar parado, corre o workflow a mao.
- Se o blog mudar de tema e os comentarios deixarem de ser HTML estatico, o
  parser em `blogger_comments.py` tem de ser ajustado.
