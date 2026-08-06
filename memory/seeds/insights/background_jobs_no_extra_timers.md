---
name: background_jobs_no_extra_timers
description: When you offload a job to the background, don't set extra timers to poll for it — wait for the system's completion notification
type: feedback
hall: advice
source: palace_init
---
# Don't busy-poll background jobs

When you send a long task to the background (an offloaded job, a detached run,
a scan), **do not set additional timers or sleep-loops waiting for the result**.
The system notifies you automatically when the job finishes.

**Why:** extra timers create duplicate notifications, waste turns, and can wake
you to poll something that will notify you anyway. Wait for the completion signal
instead of proactively guessing when it'll be done.

Exception: if you're waiting on something the runtime genuinely can't notify you
about (an external service, a remote queue), pick a poll interval matched to how
fast that state actually changes — not a tight loop.
