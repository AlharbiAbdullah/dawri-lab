
select d::date as date_day
from generate_series(date '2011-01-01', date '2030-12-31', interval 1 day) as t(d)
