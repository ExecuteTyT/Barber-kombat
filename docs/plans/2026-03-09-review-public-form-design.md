# Public Review Form — Design

## URL Format
```
/review?branch=UUID&barber=UUID&visit=UUID
```
`visit` is optional. When present, the review is linked to a specific YClients visit.

## Screens

### Screen 1: Review Form
- Header: branch name + address
- Barber name: large, centered
- 5 interactive stars (gold when selected, gray otherwise, scale animation on tap)
- Textarea for comment (appears after rating selected, max 1000 chars, optional)
- Submit button: gold, disabled until rating selected, spinner on submit
- localStorage guard: soft warning if already submitted from this browser

### Screen 2: Thank You
- Animated green checkmark
- "Спасибо за отзыв!" heading
- "Ваше мнение помогает нам стать лучше" subtext
- No further actions — terminal screen

### Error States
- Invalid/missing UUIDs in URL → "Ссылка недействительна"
- Server error → "Не удалось отправить, попробуйте позже" + retry button
- Barber not found in branch → "Ссылка недействительна"

## New Backend Endpoint
```
GET /api/v1/reviews/info?branch=UUID&barber=UUID
→ { barber_name, branch_name, branch_address }
```
Public, no auth. Returns display info for the review form.

## Frontend
- New file: `frontend/src/screens/public/ReviewPublicScreen.tsx`
- Route `/review` added to App.tsx BEFORE auth check
- No dependencies on Zustand, authStore, or Telegram SDK
- Uses direct axios/fetch without Bearer token
- Mobile-first layout, max-width 480px centered
- Dark theme using existing CSS variables

## Existing Backend
- `POST /api/v1/reviews/submit` already accepts ReviewCreate schema
- Schema: { branch_id, barber_id, visit_id?, client_id?, rating(1-5), comment?, source }
- source = "form" for this page
