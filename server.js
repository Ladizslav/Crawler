const express = require('express');
const { MongoClient, ObjectId } = require('mongodb');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json());

const uri = "mongodb://localhost:27017";
const client = new MongoClient(uri);

// Get single article by ID
app.get('/api/articles/:id', async (req, res) => {
  try {
    await client.connect();
    const db = client.db("webnews");
    
    const article = await db.collection("idnes").findOne({
      _id: new ObjectId(req.params.id)
    });

    if (!article) {
      return res.status(404).json({ error: "Article not found" });
    }

    res.json(article);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Invalid article ID" });
  }
});

// Get all articles with pagination
app.get('/api/articles', async (req, res) => {
  try {
    await client.connect();
    const db = client.db("webnews");
    
    const page = parseInt(req.query.page) || 1;
    const limit = 1; // 1 article per page
    const skip = (page - 1) * limit;

    const [articles, total] = await Promise.all([
      db.collection("idnes")
        .find({})
        .skip(skip)
        .limit(limit)
        .toArray(),
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
    console.error(err);
    res.status(500).json({ error: "Server error" });
  }
});

app.listen(3001, '0.0.0.0', () => {
  console.log('API running on port 3001');
});