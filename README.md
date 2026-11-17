# Comentarios completos do Eurogenes para o NewsBlur

O Blogger corta o texto de todos os comentarios no feed RSS/Atom/JSON aos ~400
caracteres. O texto completo existe no HTML do post, 200 comentarios por pagina
(`?commentPage=N`). Este script monta um feed Atom novo, com o texto inteiro,
dos comentarios mais recentes de todos os posts.

`feed.xml` e gerado no GitHub Actions a cada 30 minutos e publicado no GitHub
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

- Le o feed de comentarios do blog (`feeds/comments/default`, max 500) para
  saber o que e novo.
- Agrupa por post e vai buscar so as paginas necessarias do HTML do post
  (`?commentPage=N`) para obter o texto completo.
- Gera um Atom com `<id>` estavel (`comment-<id>`), por isso reescrever o feed
  inteiro nao duplica nada no leitor.
- O `<updated>` do feed e a data do comentario mais recente, nao a hora do
  build: se nao ha comentarios novos, o ficheiro sai igual e o workflow nao faz
  commit.

## Uso local

```bash
python3 blogger_comments.py URL                          # ultimos 10, completos
python3 blogger_comments.py URL -n 30                    # ultimos 30
python3 blogger_comments.py URL --id 4482474905892692466 # um comentario (id do #c<id> do RSS)
python3 blogger_comments.py URL --page 3                 # uma pagina (200)
python3 blogger_comments.py https://eurogenes.blogspot.com --blog -n 300 --feed > feed.xml
```

So precisa de Python 3 (biblioteca standard, sem dependencias).

## Notas

- O cron do GitHub nao e pontual: `*/30` costuma correr a cada 30-60 min, e as
  vezes salta um. Nao ha problema, os comentarios nao se perdem.
- Workflows agendados sao desactivados ao fim de 60 dias sem actividade no
  repositorio. Como o proprio workflow faz commit quando ha comentarios novos,
  isso normalmente nao acontece; se o blog ficar parado, corre o workflow a mao.
- Se o blog mudar de tema e os comentarios deixarem de ser HTML estatico, o
  parser em `blogger_comments.py` tem de ser ajustado.
