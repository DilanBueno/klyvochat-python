import mysql from 'mysql2/promise';

let pool = null;

export async function initDatabase(config) {
  pool = mysql.createPool({
    host: config.db.host,
    port: config.db.port,
    user: config.db.user,
    password: config.db.password,
    database: config.db.name,
    waitForConnections: true,
    connectionLimit: 10,
  });
  
  await pool.query(`
    CREATE TABLE IF NOT EXISTS users (
      id VARCHAR(36) PRIMARY KEY,
      username VARCHAR(255) NOT NULL,
      email VARCHAR(255) UNIQUE NOT NULL,
      password_hash VARCHAR(255) NOT NULL,
      public_key TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `);

  await pool.query(`
    CREATE TABLE IF NOT EXISTS friend_requests (
      id VARCHAR(36) PRIMARY KEY,
      requester_id VARCHAR(36) NOT NULL,
      addressee_id VARCHAR(36) NOT NULL,
      status ENUM('pending', 'accepted', 'rejected') NOT NULL DEFAULT 'pending',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      UNIQUE KEY uq_friend_request_pair (requester_id, addressee_id),
      KEY idx_friend_requests_addressee (addressee_id, status),
      KEY idx_friend_requests_requester (requester_id, status)
    )
  `);

  await pool.query(`
    CREATE TABLE IF NOT EXISTS friendships (
      id VARCHAR(36) PRIMARY KEY,
      requester_id VARCHAR(36) NOT NULL,
      addressee_id VARCHAR(36) NOT NULL,
      status ENUM('accepted') NOT NULL DEFAULT 'accepted',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      UNIQUE KEY uq_friendship_pair (requester_id, addressee_id),
      KEY idx_friendships_requester (requester_id, status),
      KEY idx_friendships_addressee (addressee_id, status)
    )
  `);
  
  console.log('Database initialized');
  return pool;
}

export function getPool() {
  return pool;
}
