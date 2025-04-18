const express = require('express');
const { MongoClient, ObjectId } = require('mongodb');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json());

const uri = "mongodb://localhost:27017";
const client = new MongoClient(uri);

// API endpointy
app.get('/api/articles/:id', async (req, res) => {
  try {
    await client.connect();
    const db = client.db("webnews");
    const article = await db.collection("idnes").findOne({
      _id: new ObjectId(req.params.id)
    });
    res.json(article || {});
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/articles', async (req, res) => {
  try {
    await client.connect();
    const db = client.db("webnews");
    const page = parseInt(req.query.page) || 1;
    const limit = 1;
    const skip = (page - 1) * limit;

    const [articles, total] = await Promise.all([
      db.collection("idnes").find({}).skip(skip).limit(limit).toArray(),
      db.collection("idnes").estimatedDocumentCount()
    ]);

    res.json({
      currentArticle: articles[0],
      currentPage: page,
      totalPages: Math.ceil(total / limit),
      nextPage: page < Math.ceil(total / limit) ? page + 1 : null,
      prevPage: page > 1 ? page - 1 : null
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// HTML frontend
app.get('/', (req, res) => {
  res.send(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>Články</title>
      <style>
        body { font-family: Arial; max-width: 800px; margin: 0 auto; padding: 20px; }
        #article-content { white-space: pre-wrap; margin: 20px 0; line-height: 1.6; }
        .navigation { display: flex; justify-content: space-between; margin-top: 20px; }
        button { padding: 8px 16px; }
      </style>
    </head>
    <body>
      <h1 id="article-title">Načítání...</h1>
      <div id="article-content"></div>
      <div class="navigation">
        <button id="prevBtn">Předchozí</button>
        <span id="pageInfo">Stránka 1</span>
        <button id="nextBtn">Další</button>
      </div>
      <script>
        let currentPage = 1;
        let totalPages = 1;
        
        async function loadPage(page) {
          const res = await fetch('/api/articles?page=' + page);
          const data = await res.json();
          if (data.currentArticle) {
            document.getElementById('article-title').textContent = data.currentArticle.title || 'Bez názvu';
            document.getElementById('article-content').textContent = data.currentArticle.content || '';
            currentPage = data.currentPage;
            totalPages = data.totalPages;
            document.getElementById('pageInfo').textContent = 'Stránka ' + currentPage + ' z ' + totalPages;
            document.getElementById('prevBtn').disabled = currentPage <= 1;
            document.getElementById('nextBtn').disabled = currentPage >= totalPages;
          }
        }
        
        document.getElementById('prevBtn').onclick = () => currentPage > 1 && loadPage(currentPage - 1);
        document.getElementById('nextBtn').onclick = () => currentPage < totalPages && loadPage(currentPage + 1);
        
        loadPage(1);
      </script>
    </body>
    </html>
  `);
});

app.listen(3001, '0.0.0.0', () => console.log('Server běží na portu 3001'));