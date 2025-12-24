# Archived: AWS Textract Multi-Currency OCR

**Status:** Production-ready but not deployed
**Reason:** Architecture simplified to single OCR (Odoo only)
**Date Archived:** December 2025

## Why Archived

- Client decision to use Odoo built-in OCR as single source of truth
- Reduces complexity (no dual OCR consensus needed)
- Reduces cost (no AWS Textract API charges)
- Odoo OCR proven sufficient for client's use case

## Future Use Cases

- Keep this code if client wants to add Textract back
- Useful for multi-vendor OCR comparison projects
- Reference implementation for ISO 4217 currency handling

## Technical Highlights

- 170+ currencies supported (ISO 4217 standard)
- Smart filtering (exchange rates, decimal errors)
- Multi-language TOTAL keyword detection
- Zero maintenance needed
