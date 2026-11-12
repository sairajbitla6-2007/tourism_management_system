-- Adds one-time password reset token storage for existing databases.
-- Apply once to tourism_db; this does not modify existing user passwords.

USE tourism_db;

CREATE TABLE password_reset_tokens (
    user_id INT PRIMARY KEY,
    token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
    requested_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL,
    CONSTRAINT fk_password_reset_tokens_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_password_reset_expiry (expires_at)
) ENGINE=InnoDB;
