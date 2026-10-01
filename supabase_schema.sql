
-- Supabase schema for live GeoAI classroom mode.
create table if not exists public.participants (
  room text not null,
  session_id text not null,
  name text not null,
  last_seen bigint not null,
  mission integer default 1,
  completed_m1 boolean default false,
  primary key (room, session_id)
);

alter table public.participants enable row level security;

-- For a controlled classroom prototype only.
-- Replace with authenticated policies before production deployment.
create policy "classroom read" on public.participants for select using (true);
create policy "classroom insert" on public.participants for insert with check (true);
create policy "classroom update" on public.participants for update using (true) with check (true);

create index if not exists participants_room_seen_idx
on public.participants(room,last_seen);
