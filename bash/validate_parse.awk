BEGIN {
	IFS=""
	OFS=","

	# defining event templates as strings for regex matching

	# NOTE: using stricter patterns here:
	# - strictly numeric fields => [0-9] or [0-9-]
	# - basic IPv4 matching => [0-9]{1,3}(\.[0-9]{1,3}){3}

	# using \\ => for escaping string parser and regex parser
    templates["E1"] = "^jk2_init\\(\\) Found child [0-9]* in scoreboard slot [0-9]*"
    templates["E2"] = "^workerEnv\\.init\\(\\) ok .*"
    templates["E3"] = "^mod_jk child workerEnv in error state [0-9]*"
    templates["E4"] = "^\\[client [0-9]{1,3}(\\.[0-9]{1,3}){3}\\] Directory index forbidden by rule: .*"
    templates["E5"] = "^jk2_init\\(\\) Can't find child [0-9]* in scoreboard"
    templates["E6"] = "^mod_jk child init [0-9-]* [0-9-]*"

	# general regex to match timestamp and event level
	# \1 = timestamp
	# \2 = event level
	# \3 = content
	# TODO: strict regex for date
	# TODO: strict regex for IPv4
	# TODO: strict regex day / month
	preproc_regex="^\\[([A-Za-z]{3} [A-Za-z]{3} [0-9]{2} [0-9:]{8} [0-9]{4})\\]\\s+\\[([a-z]+)\\]\\s+(.*)$"

	# TODO: NOTES
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
	print "LineId,Time,Level,Content,EventId" > OUTFILE	

	err = 0
}

{
	# adding empty line check here
	if ($0 ~ /^\s*$/) {
		# TODO
		next
	}

    matched = 0
	matched_code = ""

	if (match($0, preproc_regex, groups)) {
		timestamp = groups[1]
		level = groups[2]
		content = groups[3]

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

    # Compare the remaining content against each event template.
    for (id in templates) {
        if (content ~ templates[id]) {
            # optional debugging
			# print NR " #" valid_count " [MATCH - " id "] " $0
			match_count++
			matched_id = id
            matched = 1
            break
        }
    }

    # If none of the templates matched, then the log line is considered unmatched.
    if (matched == 0)
        # optional debugging
		# print NR " #" (NR-valid_count) " [NO MATCH] " $0

	# writing to csv
	# TODO: FOR SOME REASON, BELOW CMD DOES NOT PRINT TO STDOUT
	# TODO: BUT IF I REMOVE IT, THE NEXT (AND INTEGRAL) CMD DOES NOT WORK EITHER 
	print(valid_count, timestamp, level, content, matched_id)
	print(valid_count, timestamp, level, content, matched_id) >> OUTFILE
}

END {
	if (err)
		exit err
	
	print "logfile is valid apache error log"
}
