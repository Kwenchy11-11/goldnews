


def format_actionable_alert(
    event_name: str,
    actual,
    forecast,
    previous,
    composite_score: float,
    confidence: float,
    trade_decision: str,
    reasoning: str = None,
    alert_priority: str = "normal"
) -> str:
    """
    Format an actionable trading alert with clear bias and instructions.
    
    This format focuses on helping users make trading decisions rather than
    just showing scores. Includes entry timing, invalidation levels, and
    risk management guidance.
    
    Args:
        event_name: Name of the economic event
        actual: Actual released value
        forecast: Forecast value
        previous: Previous value
        composite_score: Impact score (-10 to +10)
        confidence: Confidence level (0-100)
        trade_decision: SELL_GOLD, BUY_GOLD, WAIT, NO_TRADE
        reasoning: Thai reasoning text
        alert_priority: immediate, high, normal, low
        
    Returns:
        Formatted actionable alert message
    """
    import html
    
    # Determine bias and direction
    if composite_score >= 5.5:
        bias = "SELL GOLD"
        bias_thai = "🔴 ขายทองคำ"
        direction_emoji = "🔴"
        price_action = "ลง"
    elif composite_score >= 2:
        bias = "SELL GOLD"
        bias_thai = "🟠 ขายทองคำ (อ่อน)"
        direction_emoji = "🟠"
        price_action = "ลง"
    elif composite_score <= -5.5:
        bias = "BUY GOLD"
        bias_thai = "🟢 ซื้อทองคำ"
        direction_emoji = "🟢"
        price_action = "ขึ้น"
    elif composite_score <= -2:
        bias = "BUY GOLD"
        bias_thai = "🟡 ซื้อทองคำ (อ่อน)"
        direction_emoji = "🟡"
        price_action = "ขึ้น"
    else:
        bias = "NEUTRAL"
        bias_thai = "⚪ เฝ้าดู"
        direction_emoji = "⚪"
        price_action = "ไม่มีทิศทางชัดเจน"
    
    # Alert urgency
    urgency_emoji = "🚨" if alert_priority in ["immediate", "high"] else "📢"
    
    # Calculate surprise deviation
    surprise_text = ""
    if actual and forecast:
        try:
            actual_val = float(str(actual).replace('%', '').replace('K', ''))
            forecast_val = float(str(forecast).replace('%', '').replace('K', ''))
            deviation = ((actual_val - forecast_val) / abs(forecast_val)) * 100 if forecast_val != 0 else 0
            
            if abs(deviation) >= 20:
                surprise_text = "สูงมาก" if deviation > 0 else "ต่ำมาก"
            elif abs(deviation) >= 10:
                surprise_text = "สูงกว่าคาด" if deviation > 0 else "ต่ำกว่าคาด"
            elif abs(deviation) >= 5:
                surprise_text = "สูงเล็กน้อย" if deviation > 0 else "ต่ำเล็กน้อย"
            else:
                surprise_text = "ใกล้เคียงคาด"
        except:
            surprise_text = "ไม่สามารถคำนวณได้"
    
    # Build the actionable alert
    message = f"""
{urgency_emoji} <b>GOLD NEWS IMPACT ALERT</b> {urgency_emoji}
{'─' * 35}

<b>📰 ข่าว:</b> {event_name}
<b>📊 ผลจริง:</b> {actual or 'N/A'}
<b>📈 คาดการณ์:</b> {forecast or 'N/A'}
<b>⚡ Surprise:</b> {surprise_text}

{'─' * 35}
<b>🎯 ผลต่อทองคำ:</b>
{bias_thai}
<b>🎚️ Confidence:</b> {confidence:.0f}/100
<b>📊 Impact Level:</b> {get_impact_level_from_score(abs(composite_score))}

{'─' * 35}
<b>💡 เหตุผล:</b>
{reasoning or _generate_default_reasoning(event_name, composite_score, actual, forecast)}

{'─' * 35}
<b>📋 คำแนะนำระบบ:</b>
"""
    
    # Add actionable advice based on decision - v0.2 uses bias/scenario language
    # NOT "เข้า Buy/Sell ทันที" - this is pre-production
    if "SELL" in bias or trade_decision in ["sell", "strong_sell"]:
        message += f"""<b>📊 Gold Bias:</b> BEARISH (ทองมีแนวโน้มลง)
<b>📌 Scenario:</b> หาก USD แข็งค่าต่อเนื่อง → ทองมีแนวโน้มย่อตัว
<b>⏰ Timing:</b> WAIT 1-3 นาที หลัง spike เพื่อยืนยันทิศทาง
<b>🛑 Invalidation:</b> ถ้าราคากลับมายืนเหนือ pre-news high → bias ไม่valid
<b>⚠️ Note:</b> นี่คือ bias จากข้อมูล ไม่ใช่สัญญาณเทรด (v{config.VERSION})
"""
    elif "BUY" in bias or trade_decision in ["buy", "strong_buy"]:
        message += f"""<b>📊 Gold Bias:</b> BULLISH (ทองมีแนวโน้มขึ้น)
<b>📌 Scenario:</b> หาก USD อ่อนค่าต่อเนื่อง → ทองมีแนวโน้มปรับตัวขึ้น
<b>⏰ Timing:</b> WAIT 1-3 นาที หลัง spike เพื่อยืนยันทิศทาง
<b>🛑 Invalidation:</b> ถ้าราคาหลุดต่ำกว่า pre-news low → bias ไม่valid
<b>⚠️ Note:</b> นี่คือ bias จากข้อมูล ไม่ใช่สัญญาณเทรด (v{config.VERSION})
"""
    elif trade_decision == "wait":
        message += f"""<b>📊 Gold Bias:</b> UNCLEAR (ทิศทางไม่ชัดเจน)
<b>📌 Scenario:</b> รอดู confirmation ก่อนตัดสินใจ
<b>💡 Reason:</b> ข้อมูลยังไม่ชัดเจนพอหรือมีความขัดแย้ง
<b>📍 Action:</b> เฝ้าดูราคา ไม่เข้า position ในตอนนี้
<b>⚠️ Note:</b> v{config.VERSION} - ยังอยู่ในช่วงทดสอบ
"""
    else:
        message += f"""<b>📊 Gold Bias:</b> NEUTRAL (ไม่มี bias ชัดเจน)
<b>💡 Reason:</b> คะแนนไม่ผ่านเกณฑ์ minimum threshold
<b>📍 Action:</b> ข้ามข่าวนี้ รอโอกาสถัดไป
<b>⚠️ Note:</b> v{config.VERSION} - ยังอยู่ในช่วงทดสอบ
"""
    
    message += f"\n{'─' * 35}"
    
    return message


def get_impact_level_from_score(score: float) -> str:
    """Get impact level description from score."""
    if score >= 7:
        return "สูงมาก (High)"
    elif score >= 5:
        return "สูง (High)"
    elif score >= 3:
        return "ปานกลาง (Medium)"
    else:
        return "ต่ำ (Low)"


def _generate_default_reasoning(event_name: str, composite_score: float, actual, forecast) -> str:
    """Generate default Thai reasoning based on event and score."""
    if composite_score >= 5:
        return f"• ข้อมูล {event_name} แข็งแกร่งกว่าคาด → กดดันทองคำ\n• USD อาจแข็งค่า → ทองลง\n• Surprise score สูงพอสำหรับ post-event alert"
    elif composite_score >= 2:
        return f"• ข้อมูล {event_name} ดีกว่าคาดเล็กน้อย\n• มีแรงกดดันต่อทองคำ แต่ไม่แรงมาก\n• ควรระวังความผันผวน"
    elif composite_score <= -5:
        return f"• ข้อมูล {event_name} อ่อนแอกว่าคาด → หนุนทองคำ\n• USD อาจอ่อนค่า → ทองขึ้น\n• Surprise score สูงพอสำหรับ post-event alert"
    elif composite_score <= -2:
        return f"• ข้อมูล {event_name} อ่อนกว่าคาดเล็กน้อย\n• มีแรงหนุนทองคำ แต่ไม่แรงมาก\n• ควรระวังความผันผวน"
    else:
        return f"• ข้อมูล {event_name} ใกล้เคียงคาด\n• ไม่มีผลกระทบรุนแรงต่อทองคำ\n• แนะนำให้งดเทรด"
