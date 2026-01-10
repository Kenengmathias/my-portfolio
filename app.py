from urllib.parse import quote_plus
user = "dbuser"
password = 'Z)k@QHj^eN?{ag4"mathiaskeneng2036database-password39jfn'
enc = quote_plus(password)              # -> 'P%40ss%3Aword%2Fwith%3Fchars%23'


DATABASE_URI=f"postgresql://postgres.hleoaapgefsrfvudxexa:{enc}@aws-1-eu-west-1.pooler.supabase.com:5432/postgres"
print(DATABASE_URI)
