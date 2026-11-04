-- ===== ECADEMY ACCESS v2: self-serve payments + device self-service =====
-- Paste this whole file in Supabase > SQL Editor > New query > Run.
-- Safe to run more than once.

create table if not exists public.payments (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  email text not null,
  name text,
  phone text,
  package text not null check (package in ('J','C','A')),
  amount text,
  method text not null default 'gcash',
  ref_no text,
  proof_path text,
  aff_code text references public.affiliates(code),
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  note text,
  created_at timestamptz not null default now(),
  reviewed_at timestamptz
);
alter table public.payments enable row level security;
create index if not exists payments_user_idx on public.payments(user_id, created_at desc);
create index if not exists payments_status_idx on public.payments(status, created_at desc);
drop policy if exists "payments read own" on public.payments;
create policy "payments read own" on public.payments for select to authenticated using (user_id = (select auth.uid()));
grant select on public.payments to authenticated;

create or replace function public.submit_payment(p_package text, p_name text, p_phone text, p_amount text, p_ref text, p_proof text, p_aff text)
returns json language plpgsql security definer set search_path = public as $$
declare v_uid uuid := auth.uid(); v_email text; v_aff text := null; v_id bigint;
begin
  if v_uid is null then return json_build_object('ok', false, 'message', 'Please log in first.'); end if;
  if p_package not in ('J','C','A') then return json_build_object('ok', false, 'message', 'Choose a package.'); end if;
  if coalesce(length(trim(p_ref)), 0) < 4 then return json_build_object('ok', false, 'message', 'Enter the GCash reference number.'); end if;
  if exists (select 1 from payments where user_id = v_uid and status = 'pending') then
    return json_build_object('ok', false, 'message', 'You already have a payment waiting for review. We will activate your access as soon as it is checked.');
  end if;
  select email into v_email from auth.users where id = v_uid;
  if p_aff is not null and exists (select 1 from affiliates where code = upper(p_aff) and active) then v_aff := upper(p_aff); end if;
  insert into payments (user_id, email, name, phone, package, amount, ref_no, proof_path, aff_code)
  values (v_uid, lower(v_email), left(nullif(trim(p_name),''),120), left(nullif(trim(p_phone),''),40), p_package, left(nullif(trim(p_amount),''),40), left(trim(p_ref),80), left(p_proof,200), v_aff)
  returning id into v_id;
  return json_build_object('ok', true, 'id', v_id);
end $$;
revoke execute on function public.submit_payment(text,text,text,text,text,text,text) from anon, public;
grant execute on function public.submit_payment(text,text,text,text,text,text,text) to authenticated;

create or replace function public.my_status()
returns json language sql stable security definer set search_path = public as $$
  select json_build_object(
    'member', (select row_to_json(m) from (select package, expires_at, revoked, name from members where user_id = auth.uid()) m),
    'pending', (select row_to_json(p) from (select id, package, amount, ref_no, created_at from payments where user_id = auth.uid() and status = 'pending' order by created_at desc limit 1) p),
    'rejected', (select row_to_json(p) from (select id, package, note, reviewed_at from payments where user_id = auth.uid() and status = 'rejected' and reviewed_at > now() - interval '14 days' order by reviewed_at desc limit 1) p),
    'admin', exists (select 1 from admins a join auth.users u on lower(u.email) = lower(a.email) where u.id = auth.uid())
  );
$$;
revoke execute on function public.my_status() from anon, public;
grant execute on function public.my_status() to authenticated;

create table if not exists public.device_resets (
  user_id uuid not null references auth.users(id) on delete cascade,
  at timestamptz not null default now()
);
alter table public.device_resets enable row level security;

create or replace function public.my_devices()
returns json language sql stable security definer set search_path = public as $$
  select json_build_object(
    'devices', coalesce((select json_agg(json_build_object('device_id', d.device_id, 'kind', d.kind, 'label', d.label, 'first_seen', d.first_seen, 'last_seen', d.last_seen) order by d.last_seen desc) from devices d where d.user_id = auth.uid()), '[]'::json),
    'active', (select device_id from active_device where user_id = auth.uid()),
    'next_reset', (select max(at) + interval '7 days' from device_resets where user_id = auth.uid())
  );
$$;
revoke execute on function public.my_devices() from anon, public;
grant execute on function public.my_devices() to authenticated;

create or replace function public.remove_my_device(p_device text)
returns json language plpgsql security definer set search_path = public as $$
declare v_uid uuid := auth.uid(); v_last timestamptz; v_admin boolean;
begin
  if v_uid is null then return json_build_object('ok', false, 'message', 'Please log in.'); end if;
  if not exists (select 1 from devices where user_id = v_uid and device_id = p_device) then
    return json_build_object('ok', false, 'message', 'That device is not on your account.');
  end if;
  select exists(select 1 from admins a join auth.users u on lower(u.email) = lower(a.email) where u.id = v_uid) into v_admin;
  select max(at) into v_last from device_resets where user_id = v_uid;
  if not v_admin and v_last is not null and v_last > now() - interval '7 days' then
    return json_build_object('ok', false, 'message', 'You can remove one device every 7 days. Next removal: ' || to_char((v_last + interval '7 days') at time zone 'Asia/Manila', 'DD Mon YYYY HH24:MI') || ' (PH time). Message ECADEMY if you need it sooner.');
  end if;
  delete from devices where user_id = v_uid and device_id = p_device;
  delete from active_device where user_id = v_uid and device_id = p_device;
  if not v_admin then insert into device_resets(user_id) values (v_uid); end if;
  return json_build_object('ok', true);
end $$;
revoke execute on function public.remove_my_device(text) from anon, public;
grant execute on function public.remove_my_device(text) to authenticated;

-- tidy the security advisor warnings
alter function public.device_kind(text) set search_path = public;
revoke execute on function public.claim_device(text,text) from anon, public;
revoke execute on function public.my_active_device() from anon, public;

-- private bucket for GCash screenshots: student uploads to own folder, admin views via signed URL
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('payproofs', 'payproofs', false, 5242880, array['image/jpeg','image/png','image/webp'])
on conflict (id) do nothing;
drop policy if exists "payproof upload own" on storage.objects;
create policy "payproof upload own" on storage.objects for insert to authenticated
  with check (bucket_id = 'payproofs' and (storage.foldername(name))[1] = (select auth.uid())::text);
drop policy if exists "payproof read own" on storage.objects;
create policy "payproof read own" on storage.objects for select to authenticated
  using (bucket_id = 'payproofs' and (storage.foldername(name))[1] = (select auth.uid())::text);

select 'ACCESS v2 database ready' as result;
