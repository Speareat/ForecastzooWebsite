CREATE TABLE parameters (
  name TEXT PRIMARY KEY NOT NULL,
  value TEXT NOT NULL
);

CREATE TABLE users (
  id serial PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL
);

CREATE TABLE preds (
  id serial PRIMARY KEY,
  author_id INTEGER NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  title TEXT NOT NULL,
  body TEXT,
  pred1 INTEGER NOT NULL,
  pred2 INTEGER NOT NULL,
  pred3 INTEGER NOT NULL,
  pred4 INTEGER NOT NULL,
  pred5 INTEGER NOT NULL,
  pred6 INTEGER NOT NULL,
  pred7 INTEGER NOT NULL,
  pred8 INTEGER NOT NULL,
  pred9 INTEGER NOT NULL,
  pred10 INTEGER NOT NULL,
  pred11 INTEGER NOT NULL,
  pred12 INTEGER NOT NULL,
  pred13 INTEGER NOT NULL,
  pred14 INTEGER NOT NULL,
  pred15 INTEGER NOT NULL,
  pred16 INTEGER NOT NULL,
  pred17 INTEGER NOT NULL,
  pred18 INTEGER NOT NULL,
  pred19 INTEGER NOT NULL,
  pred20 INTEGER NOT NULL,
  pred21 INTEGER NOT NULL,
  pred22 INTEGER NOT NULL,
  pred23 INTEGER NOT NULL,
  pred24 INTEGER NOT NULL,
  pred25 INTEGER NOT NULL,
  pred26 INTEGER NOT NULL,
  pred27 INTEGER NOT NULL,
  pred28 INTEGER NOT NULL,
  pred29 INTEGER NOT NULL,
  pred30 INTEGER NOT NULL,
  FOREIGN KEY (author_id) REFERENCES users (id)
);