# Test Dataset Manifest — Sinagong Tableau 2026
## Source
Original directory:

```text
/Users/jtm427/Desktop/경영정보시각화 능력/2026 시나공_경영정보시각화능력_실기_태블로_실습 및 예제파일
```
## Policy
- These files are copied as local test/reference datasets for Semantic Builder and Semantic Pack fixture work.
- They are example/practice source files, not production customer data.
- Use them to test workbook scanning, sheet detection, column profiling, value dictionary candidates, metric candidates, and join/key inference.
- Tableau packaged workbook files (`.twbx`) in the original directory were not copied as primary source datasets; the direct `.xlsx` sources are the Builder fixture set.

## Files
Recursive `.xlsx` count: 20 files.

- Top-level `.xlsx` files: 16
- Nested `.xlsx` files under `와일드카드유니온실습/`: 4

| File | Size | Status | Sheets |
|---|---:|---|---|
| `2008_2024_연령별인구현황.xlsx` | 1,577,871 bytes | ok | 2008 (280r x 48c); 2009 (280r x 48c); 2010 (283r x 48c); 2011 (283r x 48c); 2012 (284r x 48c); 2013 (284r x 48c); 2014 (285r x 48c); 2015 (285r x 48c); 2016 (282r x 48c); 2017 (282r x 48c); 2018 (282r x 48c); 2019 (282r x 48c); 2020 (296r x 48c); 2021 (296r x 48c); 2022 (295r x 48c); 2023 (295r x 48c); 2024 (298r x 48c) |
| `SEILOneCompany_HR데이터.xlsx` | 73,822 bytes | ok | 직원현황 (1383r x 8c) |
| `SEILOneCompany_Sales데이터.xlsx` | 1,273,491 bytes | ok | 결제내역 (11011r x 17c); 고객정보 (795r x 4c) |
| `경제활동인구_2013_2024.xlsx` | 26,852 bytes | ok | 2013_2019 (85r x 3c); 2020 (109r x 3c); 2021 (109r x 3c); 2022 (109r x 3c); 2023 (109r x 3c); 2024 (109r x 3c) |
| `경제활동인구_2019_2024.xlsx` | 22,758 bytes | ok | 데이터 (649r x 3c) |
| `배달앱이용현황.xlsx` | 15,998 bytes | ok | 2019 (7r x 7c); 2020 (7r x 8c); 2021 (7r x 7c); 2022 (7r x 7c); 2023 (7r x 7c); 2024 (7r x 8c) |
| `서울날씨_최고기온.xlsx` | 158,637 bytes | ok | 2024 (33r x 13c); 2023 (33r x 13c); 2022 (33r x 13c); 2021 (33r x 13c); 2020 (33r x 13c); 2019 (33r x 13c); 2018 (33r x 13c); 2017 (33r x 13c); 2016 (33r x 13c); 2015 (33r x 13c); 2014 (49r x 13c); 2013 (33r x 13c); 2012 (33r x 13c); 2011 (49r x 13c); 2010 (33r x 13c); 2009 (49r x 13c); 2008 (49r x 13c); 2007 (33r x 13c); 2006 (49r x 13c); 2005 (33r x 13c); 2004 (49r x 13c); 2003 (33r x 13c); 2002 (33r x 13c); 2001 (33r x 13c); 2000 (49r x 13c) |
| `서울지하철승하차인원.xlsx` | 1,093,184 bytes | ok | 지하철 (28826r x 5c) |
| `스타벅스_구매목록.xlsx` | 49,812 bytes | ok | 결제 (397r x 6c); 구매목록 (501r x 6c) |
| `스타벅스매장데이터.xlsx` | 208,978 bytes | ok | 서울 (645r x 4c); 경기 (502r x 4c); 광주 (68r x 4c); 대구 (94r x 4c); 대전 (72r x 4c); 부산 (147r x 4c); 울산 (35r x 4c); 인천 (83r x 4c); 강원 (44r x 4c); 경남 (81r x 4c); 경북 (63r x 4c); 전남 (36r x 4c); 전북 (41r x 4c); 충남 (55r x 4c); 충북 (41r x 4c); 제주 (34r x 4c); 세종 (15r x 4c) |
| `시도별연간인구수.xlsx` | 11,819 bytes | ok | 인구수 (18r x 6c) |
| `에버랜드입장객데이터.xlsx` | 12,444 bytes | ok | 입장객수 (49r x 6c) |
| `여름가전종목.xlsx` | 78,556 bytes | ok | A종목 (1228r x 2c); B종목 (1224r x 2c) |
| `온라인쇼핑몰_판매매체별_상품군별거래액_2017_2024.xlsx` | 67,131 bytes | ok | 데이터 (79r x 99c) |
| `와일드카드유니온실습/SEILOneCompany_2022.xlsx` | 272,842 bytes | ok | 결제내역 (1951r x 18c) |
| `와일드카드유니온실습/SEILOneCompany_2023.xlsx` | 328,355 bytes | ok | 결제내역 (2380r x 18c) |
| `와일드카드유니온실습/SEILOneCompany_2024.xlsx` | 396,347 bytes | ok | 결제내역 (2904r x 18c) |
| `와일드카드유니온실습/SEILOneCompany_2025.xlsx` | 514,207 bytes | ok | 결제내역 (3809r x 18c) |
| `우리나라인구수_2021_2024.xlsx` | 1,466,945 bytes | ok | 인구 (38473r x 6c) |
| `인구동태건수_2019_2023.xlsx` | 10,117 bytes | ok | 데이터 (17r x 6c) |

## Tableau Sample Superstore

Additional copied reference dataset:

| File | Size | Status | Notes |
|---|---:|---|---|
| `tableau_superstore/Sample - Superstore.xls` | 3,428,864 bytes | ok | Legacy Tableau Superstore `.xls`; active semantic-gold benchmark target for the Builder `.xls` connector. |

Original source:

```text
/Users/jtm427/Documents/내 Tableau 리포지토리/데이터 원본/2025.2/ko_KR-APAC/Sample - Superstore.xls
```
