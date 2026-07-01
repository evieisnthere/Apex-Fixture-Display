# Fixture Display

A python flask program that uses JSON to live update a webpage with countdowns and details about upcoming games using a CSV file, styled for Apex Sports Media.

Makes use of:
- Tkinter
- Flask
- CSV
- DateTime
- Json
- BeautifulSoup (bs4)

Probably a few too many libraries, however that is yet to be seen.

To get fixtures (Currently saves to drive Z:\, however it will save to the code's directory if it can't find that), run the fixture-scraper2. Currently it's set to pull from the Casey Indoor Cricket tournament, however changing the link and league names in-code will change that and still output to the same file.
