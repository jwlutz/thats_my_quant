import requests
import zipfile
import io
import time
import os
import re
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from threading import Lock

class RateLimiter:
    """
    A token bucket rate limiter. It allows up to  ``max_calls`` within ``period`` seconds. Set to max of 5 requests per second.
    Adjust downwards if being throttled.
    """
    def __init__(self, max_calls: int, period: float) -> None:
        self.max_calls = max_calls
        self.period = period
        self.lock = Lock()
        # timestamps of recent calls
        self.calls = []

    def acquire(self) -> None:
        """Block until a new call is allowed under the rate limit."""
        with self.lock:
            now = time.perf_counter()
            # Remove timestamps older than the current period
            while self.calls and self.calls[0] <= now - self.period:
                self.calls.pop(0)
            if len(self.calls) >= self.max_calls:
                # Wait until the oldest timestamp falls outside the period
                wait = self.period - (now - self.calls[0])
                if wait > 0:
                    time.sleep(wait)
                now = time.perf_counter()
                # Remove any timestamps that have now expired
                while self.calls and self.calls[0] <= now - self.period:
                    self.calls.pop(0)
            # Record this call
            self.calls.append(time.perf_counter())


# ------------------ CONFIG ------------------
# Update the User‑Agent with your name and email address
HEADERS = {'User-Agent': 'Jeremy Cogswell jeremyfcogswell@gmail.com'}

  
RATE_LIMITER = RateLimiter(max_calls=5, period=1.0)

def get_cik(entity_name):
    """Get CIK by scraping SEC HTML page (backup method)."""
    import urllib.parse

    encoded = urllib.parse.quote_plus(entity_name)
    search_url = f"https://www.sec.gov/cgi-bin/cik_lookup?company={encoded}"
    # Use safe_get to handle transient network errors when looking up a CIK.
    # If the request fails after retries, this function will raise a ConnectionError
    # which is propagated to the caller.  This makes the code more resilient to
    # temporary SEC connectivity issues.
    r = safe_get(search_url, headers=HEADERS)
    soup = BeautifulSoup(r.text, 'html.parser')

    pre_tags = soup.find_all('pre')
    for pre in pre_tags:
        link = pre.find('a', href=True)
        if link and 'CIK=' in link['href']:
            cik_text = link.text.strip()
            return cik_text.zfill(10)  # zero‑pad to 10 digits

    raise ValueError(f"CIK not found for: {entity_name}")

def get_13f_urls_by_date(cik, start_date, end_date):
    """
    Get URLs to 13F filings (both 13F-HR and 13F-HR/A) filed between start_date and end_date (YYYY-MM-DD).
    If both an original and an amendment exist for the same reporting period, only the amendment (latest filing) is returned.
    """
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    # Wrap the network call in safe_get to retry on connection interruptions.
    response = safe_get(url, headers=HEADERS)
    filings = response.json()['filings']['recent']

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    # Dictionary to hold the latest filing per report period
    selected = {}

    # Iterate through recent filings and keep relevant 13F forms
    for form, acc_num, fdate, rep_date in zip(
        filings['form'],
        filings['accessionNumber'],
        filings['filingDate'],
        filings.get('reportDate', [])
    ):
        if form not in ('13F-HR', '13F-HR/A'):
            continue
        try:
            filing_date = datetime.strptime(fdate, "%Y-%m-%d")
        except Exception:
            continue
        if not (start_dt <= filing_date <= end_dt):
            continue

        # Determine the key by report date; fall back to filing date if report date missing
        key = rep_date if rep_date else fdate
        # Decide whether to replace existing entry: prefer amendments, then newer filing_date
        if key in selected:
            existing = selected[key]
            # If current is amendment and existing is not, replace
            if form == '13F-HR/A' and existing['form'] != '13F-HR/A':
                selected[key] = {'form': form, 'acc_num': acc_num, 'filing_date': fdate}
            # If both same form type, keep the most recent filing
            elif form == existing['form']:
                ex_date = datetime.strptime(existing['filing_date'], "%Y-%m-%d")
                if filing_date > ex_date:
                    selected[key] = {'form': form, 'acc_num': acc_num, 'filing_date': fdate}
        else:
            selected[key] = {'form': form, 'acc_num': acc_num, 'filing_date': fdate}

    results = []
    # For each selected filing, build the XML URL
    for info in selected.values():
        acc_num = info['acc_num']
        fdate = info['filing_date']
        accession = acc_num.replace('-', '')
        filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/index.json"
        try:
            # Use safe_get to fetch the index JSON for each filing.  This prevents
            # a single network hiccup from aborting the entire scraping run.
            resp = safe_get(filing_url, headers=HEADERS)
            filing_page = resp.json()
            xml_url = None
            for file in filing_page.get('directory', {}).get('item', []):
                name = file.get('name', '')
                if name.endswith('.xml') or '13f' in name.lower():
                    xml_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{name}"
                    break
            if xml_url:
                results.append((xml_url, fdate))
        except Exception as e:
            print(f"Error parsing {filing_url}: {e}")
                # We no longer sleep here because RATE_LIMITER enforces
                # the SEC call rate globally.  Explicit sleeps would slow
                # down execution unnecessarily.

    # Sort results by filing date
    results.sort(key=lambda x: x[1])
    return results

def parse_13f_xml(url):
    """Parse the 13F XML filing and return a DataFrame of holdings."""
    # Use safe_get instead of requests.get to automatically retry on connection errors
    r = safe_get(url, headers=HEADERS)
    soup = BeautifulSoup(r.content, 'lxml')

    holdings = []
    for info in soup.find_all('infotable'):
        data = {
            'nameOfIssuer': info.find('nameofissuer').text if info.find('nameofissuer') else None,
            'cusip': info.find('cusip').text if info.find('cusip') else None,
            'value': int(info.find('value').text) if info.find('value') else None,
            'shares': int(float(info.find('sshprnamt').text)) if info.find('sshprnamt') else None,
            'shareType': info.find('sshprnamttype').text if info.find('sshprnamttype') else None,
            'putCall': info.find('putcall').text if info.find('putcall') else None,
            'investmentDiscretion': info.find('investmentdiscretion').text if info.find('investmentdiscretion') else None,
            'votingAuthoritySole': info.find('sole').text if info.find('sole') else None,
            'votingAuthorityShared': info.find('shared').text if info.find('shared') else None,
            'votingAuthorityNone': info.find('none').text if info.find('none') else None,
        }
        holdings.append(data)

    return pd.DataFrame(holdings)

def download_13f_in_date_range(start_date, end_date, entity_name=None, save=True, data=None):
    """
    Download and parse all 13F filings (including amendments) for a given entity or data row.
    Optionally save the combined DataFrame to CSV.
    """
    if data is not None and entity_name is None:
        entity_name = data['Company Name']
    print(f"\nLooking up CIK for: {entity_name}")

    cik = get_cik(entity_name) if data is None else data['CIK'].zfill(10)
    print(f"Success: CIK found: {cik}")

   
    print(f"\nFetching 13F filings (including any amendments) from {start_date} to {end_date}...")
    urls = get_13f_urls_by_date(cik, start_date, end_date)

    if not urls:
        print("Warning: No 13F filings found in this date range.")
        return pd.DataFrame()

    all_dfs = []
    # Iterate over the list of URL tuples returned by get_13f_urls_by_date.  In
    # some implementations this list may contain 2‑tuples (url, filing_date),
    # while in others it may include additional elements such as the form type.
    for i, entry in enumerate(urls):
        # Ensure we can unpack at least the URL and filing date.  If more
        # elements are present they will be ignored; this allows backward
        # compatibility with implementations that return (url, fdate, form).
        try:
            url = entry[0]
            fdate = entry[1]
        except Exception:
            raise ValueError(
                f"Unexpected entry format at index {i}: expected at least URL and filing_date, got {entry}"
            )
        print(f"\nDownloading filing #{i+1} from {fdate}:\n{url}")
        df = parse_13f_xml(url)
        # Attach metadata columns.  We insert them at the front of the
        # DataFrame to aid readability.
        df['filing_date'] = fdate
        df['filing_url'] = url
        # Add AUM column only if provided and present in the data index
        if data is not None and hasattr(data, 'index') and ('AUM' in data.index):
            df.insert(loc=0, column='AUM', value=data['AUM'])
        df.insert(loc=0, column='CIK', value=cik)
        df.insert(loc=0, column='Company Name', value=entity_name)
        all_dfs.append(df)
        # Do not sleep here; RATE_LIMITER enforces the call rate across
        # the entire script.  Removing this sleep improves throughput
        # while still respecting the SEC rate limits.

    combined = pd.concat(all_dfs, ignore_index=True)
    print(f"\nSuccess: Total holdings extracted: {len(combined)} rows from {len(all_dfs)} filings.")

    if save:
        filename = f"{entity_name.replace(' ', '_')}_13F_{start_date}_to_{end_date}.csv"
        combined.to_csv(filename, index=False)
        print(f"Saved to: {filename}")

    return combined

# ------- Acquire Top 1000 Institutions ----------
def safe_get(url, headers=None, retries=3, sleep=1):
    for attempt in range(retries):
        try:
            # Respect the global rate limit for all network calls.  This
            # blocks only when necessary (i.e. when the configured rate
            # would otherwise be exceeded).
            RATE_LIMITER.acquire()
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                return r
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt + 1} failed for {url}: {e}")
            # On exception or non‑200 status code, wait before retrying.
            time.sleep(sleep)
    raise ConnectionError(f"Failed to get {url} after {retries} attempts")

def fetch_index(year, quarter):
    url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.zip"
    r = safe_get(url, headers=HEADERS)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    df = pd.read_csv(z.open(z.namelist()[0]), sep='|', dtype=str, skiprows=10,
                     names=['CIK', 'Company Name', 'Form', 'Date Filed', 'Filename'])
    return df

def collect_13f_entries(vals):
    entries = []
    for year, q in vals:
        print(f"Fetching index: {year} Q{q}")
        idx = fetch_index(year, q)
        df = idx[idx['Form'] == '13F-HR']
        entries.append(df)
    return pd.concat(entries, ignore_index=True)

def get_all_13f_filers(vals):
    entries = []
    for year, q in vals:
        print(f"Fetching index: {year} Q{q}")
        try:
            df = fetch_index(year, q)
            df_13f = df[df['Form'] == '13F-HR'][['CIK', 'Company Name']]
            entries.append(df_13f)
            print(f"Success: Fetched {year} Q{q}")
        except Exception as e:
            print(f"Warning: Skipped {year} Q{q}: {e}")
    result = pd.concat(entries, ignore_index=True).drop_duplicates().sort_values('CIK')
    return result

def compute_filings_aum(entries):
    records = []

    for i, row in entries.iterrows():
        cik = row['CIK'].zfill(10)
        name = row['Company Name']
        filed = row['Date Filed']
        base_txt_url = f"https://www.sec.gov/Archives/{row['Filename']}"
        filename = row['Filename']
        cik = row['CIK'].zfill(10)
        accession = filename.split('/')[-1].replace('.txt', '').replace('-', '')
        data_prefix = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}"
        try:
            r = safe_get(base_txt_url, headers=HEADERS)
            soup = BeautifulSoup(r.content, 'lxml')

            docs = soup.find_all('document')
            xml_filename = None
            for doc in docs:
                fname_f = doc.find('filename')
                fname = fname_f.contents[0].strip()
                # If the document contains any <infotable> tags, it’s the information table
                if len(fname_f.find_all('infotable')) > 0:
                    xml_filename = fname
                    break

            print(xml_filename)
            if not xml_filename:
                print(f"Warning: No INFORMATION TABLE XML found for {name}")
                continue

            xml_url = f"{data_prefix}/{xml_filename}"
            print(xml_url)
            r_xml = safe_get(xml_url, headers=HEADERS)
            soup_xml = BeautifulSoup(r_xml.content, 'lxml')

            values = [int(tag.text) for tag in soup_xml.find_all('value') if tag.text.isdigit()]
            if not values:
                print(f"Warning: No <value> entries in XML for {name}")
                continue

            total = sum(values)
            records.append({
                'CIK': cik,
                'Company': name,
                'Date': filed,
                'AUM': total,
                'Filing URL': xml_url
            })
            print(f"Success: {name} - ${total:,}")
        except Exception as e:
            print(f"Error: Error with {name} ({cik}): {e}")
    return pd.DataFrame(records)

def aggregate_aum(df):
    df['Date'] = pd.to_datetime(df['Date'])
    latest = df.sort_values('Date').groupby('CIK').tail(1)
    agg = latest[['CIK','Company','AUM','Date','Filing URL']].sort_values('AUM', ascending=False)
    return agg

def get_sec_quarters(start_date, end_date):
    """
    Convert a date range into a list of (year, quarter) tuples covering the SEC indexing scheme.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end   = datetime.strptime(end_date,   "%Y-%m-%d")

    # Determine the first and last quarters to cover the range
    if start.year <= 2023 and end.year <= 2023:
        start_year = start.year
        end_year   = end.year if end.month > 3 else end.year - 1
        start_quarter = (start.month - 1) // 3 + 1
        end_quarter   = (end.month - 1) // 3 if end.month > 3 else 4
    elif start.year <= 2023 and end.year > 2023:
        start_year = start.year
        end_year   = end.year if end.month > 3 else end.year - 1
        start_quarter = (start.month - 1) // 3 + 1
        end_quarter   = ((end.month) // 3) if end.month >= 3 else 4
    else:  # start.year > 2023
        start_year = start.year if start.month < 12 else start.year + 1
        end_year   = end.year if end.month >= 3 else end.year - 1
        start_quarter = ((start.month) // 3 + 1) if start.month < 12 else 1
        end_quarter   = ((end.month) // 3) if end.month >= 3 else 4

    vals = []
    for y in range(start_year, end_year + 1):
        if y == start_year and y != end_year:
            vals += [(y, q) for q in range(start_quarter, 5)]
        elif y == start_year and y == end_year:
            vals += [(y, q) for q in range(start_quarter, end_quarter + 1)]
        elif start_year < y < end_year:
            vals += [(y, q) for q in range(1, 5)]
        else:  # y == end_year and y != start_year
            vals += [(y, q) for q in range(1, end_quarter + 1)]

    return vals

def compute_top_x_institutions(vals, x=1000):
    print("Collecting 13F-HR entries...")
    entries = collect_13f_entries(vals)
    print(f"Found {len(entries)} 13F-HR filings.\n")

    print("Calculating AUM from filings...")
    aum_df = compute_filings_aum(entries)
    print(f"\nSuccess: Computed AUM for {len(aum_df)} filings.")

    print("\nRanking top 13F filers...")
    top = aggregate_aum(aum_df)
    top_x = top.head(x)

    top_x_filename = f'top_{x}_13f_by_aum_{vals[0][0]}Q{vals[0][1]}_to_{vals[-1][0]}Q{vals[-1][1]}.csv'
    top_x.to_csv(top_x_filename, index=False)
    print(f"\nSaved: {top_x_filename}")
    return top_x

def compute_holdings(start: str, end: str, filers: pd.DataFrame, workers: int = 5) -> pd.DataFrame:
    """
    Download holdings for each filer in the provided DataFrame between start and end dates.
    The downloads are performed concurrently using a thread pool of size ``workers``.
    A global rate limiter ensures the SEC call rate is respected.  The concatenated
    results are saved to a CSV in the current directory.

    Args:
        start: The start date (YYYY-MM-DD).
        end:   The end date (YYYY-MM-DD).
        filers: A DataFrame of filers with columns 'CIK' and 'Company Name'.
        workers: Number of threads to use for concurrent downloads.

    Returns:
        A concatenated DataFrame containing all holdings.
    """
    from concurrent.futures import ThreadPoolExecutor

    # Each row in ``filers`` must contain the CIK and Company Name.  We use
    # ``download_13f_in_date_range`` with ``save=False`` so as not to write
    # intermediate CSVs for each filer.  The rate limiter ensures the
    # aggregate call rate across threads remains within the configured limit.
    def process_row(row):
        return download_13f_in_date_range(start, end, save=False, data=row)

    # Collect DataFrames in parallel.
    frames = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        # Use list comprehension to preserve order, but note that results
        # may complete out of order.  The final concatenation does not
        # depend on the order of results.
        futures = [executor.submit(process_row, filers.iloc[i]) for i in range(len(filers))]
        for future in futures:
            try:
                frames.append(future.result())
            except Exception as exc:
                print(f"Warning: compute_holdings failed for a filer: {exc}")

    df = pd.concat(frames, ignore_index=True)
    data_filename = f'{start} to {end} 13f data.csv'
    df.to_csv(data_filename, index=False)
    print(f"\nSaved: {data_filename}")
    return df
if __name__ == "__main__":
    start_date = input('Enter start date (yyyy-mm-dd): ')
    end_date   = input('Enter end date (yyyy-mm-dd): ')
    vals = get_sec_quarters(start_date, end_date)

    # Compute holdings for all filers
    all_filers_df = get_all_13f_filers(vals)
    compute_holdings(start_date, end_date, all_filers_df)
