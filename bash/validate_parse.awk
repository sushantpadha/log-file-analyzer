BEGIN {
	FS=""    # read whole line as field
	OFS=","  # write csv with comma delimiter

	# defining event templates as strings for regex matching

	# NOTE:
	# - basic IPv4 matching => [0-9]{1,3}(\.[0-9]{1,3}){3}

	# reading template strings from file for modularity

	fpath = "bash/template-data/apache_re"
	i = 0
	while ((getline line < fpath) > 0) {
		i++
		template_re["E" i] = line
	}
	close(fpath)

	fpath = "bash/template-data/apache_str"
	i = 0
	while ((getline line < fpath) > 0) {
		i++
		template_str["E" i] = line
	}
	close(fpath)


	# stricter regex (better timestamp checking)
	# \1 = timestamp
	# \2 = dayname
	# \3 = monthname
	# \4 = day
	# \5 = hour
	# \6 = year
	# \7 = level
	# \8 = content

	# must check:
	# 1. dayname	- regex
	# 2. monthname	- regex
	# 3. day		- later
	# 4. hr,min,sec	- regex
	# 4. year		- regex, basic (4-digit code starting w 1/2)

	preproc_regex="^\\[((Sun|Mon|Tue|Wed|Thu|Fri|Sat) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) ([0-9]{2}) ([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9] ([12][0-9]{3}))\\]\\s+\\[([a-z]+)\\]\\s+(.*)$"

	# NOTES
	# 1. valid log entry is of the form:
	#	`[timestamp] [level] content` where timestamp and level and roughly fixed format as encoded in regex
	# 2. if valid, an entry may match one of the known templates
	# 3. if it doesn't, the template field is left blank
	# 4. empty lines are ignored
	#	(optionally, may implement user-controlled toggle whether to count them as invalid)
	# 5. a file is considered VALID apache error logfile iff
	#	i)	all lines are valid

	valid_count=0
	match_count=0

	# set header for csv
	print "LineId,Time,Level,Content,EventId,EventTemplate" > OUTFILE	

	err = 0
}

{
	# adding empty line check here
	if ($0 ~ /^\s*$/) {
		# skip
		next
	}

	valid = 0
    matched = 0
	matched_code = ""
	matched_template = ""

	# using match to extract captured groups as well
	if (match($0, preproc_regex, groups)) {
		timestamp = groups[1]
		dayname = groups[2]
		monthname = groups[3]
		day = groups[4] + 0   # convert to number
		hour = groups[5] + 0
		year = groups[6] + 0
		level = groups[7]
		content = groups[8]

		valid = 1

		# motnh map
		days_in_month["Jan"] = 31
		days_in_month["Feb"] = 28
		days_in_month["Mar"] = 31
		days_in_month["Apr"] = 30
		days_in_month["May"] = 31
		days_in_month["Jun"] = 30
		days_in_month["Jul"] = 31
		days_in_month["Aug"] = 31
		days_in_month["Sep"] = 30
		days_in_month["Oct"] = 31
		days_in_month["Nov"] = 30
		days_in_month["Dec"] = 31

		# leap year adjustment
		if (monthname == "Feb" && ((year % 4 == 0 && year % 100 != 0) || (year % 400 == 0))) {
			days_in_month["Feb"] = 29
		}

		# validate
		if (!(day >= 1 && day <= days_in_month[monthname])) {
			printf "(day not in range) " 
			valid = 0
		}
	}

	if (valid) {
		valid_count++

		# optional debugging

		# print "Timestamp: " timestamp
		# print "Level: " level
		# print "Content: " content
		# print "-------------------"
	} else {
		# ! print invalid, erase csv and quit
		print "invalid log line at " NR " : " $0
		print "" > OUTFILE
		err = 1
		exit
	}

    # compare the remaining content against each event template.
    for (id in template_re) {
        if (content ~ template_re[id]) {
            # optional debugging
			# print NR " #" valid_count " [MATCH - " id "] " $0
			match_count++
			matched_id = id
			matched_template = template_str[id]
            matched = 1
            break
        }
    }

    # If none of the templates matched, then the log line is considered unmatched.
    if (matched == 0) {
        # optional debugging
		# print NR " #" (NR-valid_count) " [NO MATCH] " $0
	}

	# writing to csv
	print(valid_count, timestamp, level, content, matched_id, matched_template) >> OUTFILE
	fflush(OUTFILE)  # flushing to prevent unwanted buffering
	fflush()
}

END {
	if (err) {
		exit err
	}

	print "logfile is valid apache error log"
	fflush()
}
