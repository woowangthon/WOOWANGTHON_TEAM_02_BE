CREATE TABLE user_saved_notices (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notice_id BIGINT NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
    saved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, notice_id)
);

CREATE INDEX idx_user_saved_notices_notice ON user_saved_notices(notice_id);
