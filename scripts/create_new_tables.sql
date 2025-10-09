-- scripts/create_new_tables.sql - Create new tables for improvements
-- Run this script to add new tables for enhanced features

-- Technical Indicators Table
CREATE TABLE IF NOT EXISTS technical_indicators (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(15) NOT NULL,
    calc_date DATE NOT NULL,

    -- Moving Averages
    ma_5 DECIMAL(10,3),
    ma_10 DECIMAL(10,3),
    ma_20 DECIMAL(10,3),
    ma_60 DECIMAL(10,3),
    ema_12 DECIMAL(10,3),
    ema_26 DECIMAL(10,3),

    -- MACD
    macd_dif DECIMAL(10,4),
    macd_dea DECIMAL(10,4),
    macd_histogram DECIMAL(10,4),

    -- RSI
    rsi_6 DECIMAL(8,4),
    rsi_12 DECIMAL(8,4),
    rsi_24 DECIMAL(8,4),

    -- Bollinger Bands
    boll_upper DECIMAL(10,3),
    boll_middle DECIMAL(10,3),
    boll_lower DECIMAL(10,3),
    boll_width DECIMAL(10,4),

    -- KDJ
    kdj_k DECIMAL(8,4),
    kdj_d DECIMAL(8,4),
    kdj_j DECIMAL(8,4),

    -- ATR
    atr_14 DECIMAL(10,4),
    atr_normalized DECIMAL(8,4),

    -- Volume
    volume_ma_5 BIGINT,
    volume_ma_10 BIGINT,
    volume_ratio DECIMAL(8,4),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_symbol_date UNIQUE (symbol, calc_date)
);

CREATE INDEX idx_symbol_calc_date ON technical_indicators(symbol, calc_date);
CREATE INDEX idx_calc_date ON technical_indicators(calc_date);

-- Indicator Signals Table
CREATE TABLE IF NOT EXISTS indicator_signals (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(15) NOT NULL,
    signal_date DATE NOT NULL,
    signal_type VARCHAR(20) NOT NULL,
    signal_strength DECIMAL(4,3) NOT NULL,

    -- Contributing factors
    ma_signal VARCHAR(10),
    macd_signal VARCHAR(10),
    rsi_signal VARCHAR(10),
    boll_signal VARCHAR(10),
    kdj_signal VARCHAR(10),
    volume_signal VARCHAR(10),

    interpretation VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_signal_symbol_date ON indicator_signals(symbol, signal_date);
CREATE INDEX idx_signal_strength ON indicator_signals(signal_type, signal_strength);

-- Add comments
COMMENT ON TABLE technical_indicators IS 'Pre-calculated technical indicators';
COMMENT ON TABLE indicator_signals IS 'Trading signals derived from indicators';

COMMENT ON COLUMN technical_indicators.ma_5 IS '5-day moving average';
COMMENT ON COLUMN technical_indicators.boll_upper IS 'Bollinger upper band';
COMMENT ON COLUMN technical_indicators.kdj_k IS 'KDJ K value';
COMMENT ON COLUMN technical_indicators.atr_14 IS '14-day Average True Range';

-- Grant permissions (adjust as needed)
-- GRANT SELECT, INSERT, UPDATE ON technical_indicators TO your_app_user;
-- GRANT SELECT, INSERT ON indicator_signals TO your_app_user;