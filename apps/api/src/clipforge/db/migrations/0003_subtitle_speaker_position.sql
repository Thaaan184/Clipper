-- Migration 0003: Add speaker and pos_y columns to subtitle_words

ALTER TABLE subtitle_words ADD COLUMN speaker TEXT DEFAULT 'speaker_1';
ALTER TABLE subtitle_words ADD COLUMN pos_y INTEGER DEFAULT NULL;
