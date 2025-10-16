# Next Session: Chain Builder Feature - Start Here

## Quick Context
We're building a **Loan Chain Builder** feature for the media scheduler. This allows Rafael to quickly create 4-6 back-to-back vehicle assignments for a single media partner.

## What to Say to Claude
```
I want to implement the Chain Builder feature for the media scheduler.

Context:
- We have a working Optimizer that assigns vehicles to partners
- We have distance calculations, tier rankings (A+,A,B,C), and loan history
- Rafael needs to build "chains" - multiple vehicles for one partner back-to-back
- Partners often request 4-6 vehicles they haven't reviewed recently

Read CHAIN_BUILDER_PLAN.md for the full implementation plan.

Let's start with Phase 1, Commit 1: Create the chain suggestions endpoint skeleton.

Follow the commit-by-commit plan in CHAIN_BUILDER_PLAN.md. Test after each commit.
Make small commits so we can revert if needed.
```

## Key Files to Reference
- `/CHAIN_BUILDER_PLAN.md` - Complete implementation plan
- `/backend/app/routers/solver.py` - Example of how we call optimization logic
- `/backend/app/solver/candidates.py` - Building candidate pairs
- `/frontend/src/pages/Calendar.jsx` - Timeline rendering we can reuse
- `/frontend/src/pages/Optimizer.jsx` - Partner dropdown patterns

## Current Architecture Notes
- **Database:** Supabase via DatabaseService
- **Backend:** FastAPI with async/await
- **Frontend:** React with hooks
- **Styling:** Tailwind CSS
- **State:** useState, no Redux

## Git Workflow
```bash
# After each working commit:
git add <files>
git commit -m "Commit N: Description from plan"
git push origin main

# If something breaks:
git revert HEAD
git push origin main
```

## Important Constraints
- Loans are typically 7 days (configurable)
- Partners can have multiple vehicles if they don't overlap
- Max 1 vehicle per partner per day
- Must respect tier caps, cooldown periods
- Check vehicle lifecycle (in_service_date, expected_turn_in_date)

## Testing Checklist Per Commit
- [ ] Code compiles/runs
- [ ] API endpoint returns expected data
- [ ] No errors in browser console
- [ ] Existing features still work
- [ ] Can revert cleanly if needed

## Success Criteria for Chain Builder
At minimum viable:
- Select partner → Get suggested vehicles they haven't reviewed
- See timeline preview of 4-vehicle chain
- Save chain → Appears in Calendar view

Nice to have:
- Manual vehicle swaps
- Make/tier preferences
- Save chain templates
