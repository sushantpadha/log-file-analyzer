# ? need to define functions outside BEGIN block? 

# format date from csv into YYYY-MM-DD HH:MM:SS format
function format(a)
{
    # day month date time year
    split(a, _a, " ")
    
    # define moonth map
    month_map["Jan"] = "01"
    month_map["Feb"] = "02"
    month_map["Mar"] = "03"
    month_map["Apr"] = "04"
    month_map["May"] = "05"
    month_map["Jun"] = "06"
    month_map["Jul"] = "07"
    month_map["Aug"] = "08"
    month_map["Sep"] = "09"
    month_map["Oct"] = "10"
    month_map["Nov"] = "11"
    month_map["Dec"] = "12"

    # convert to YYYY-MM-DD HH:MM:SS format
    out = _a[5] "-" month_map[_a[2]] "-" _a[3] " " _a[4]
	
	return out
}

# compares two dates as a >= b
# using lexico order only
function ge(a, b)
{
	# print "> a: " a "\tb: " b
	if (a >= b) return 1;
	return 0
}

BEGIN {
	FS=",";
	OFS=",";

	# assuming input file is csv
	# assuming format is
	# LineId,Time,Level,Content,EventId (for header)
	# and appropriate format for rest of data

	# assuming three variables are defined:
	# OUTFILE = output csv fpath
	# START_DATE, END_DATE = strings of format YYYY-mm-DD HH:MM:SS

	# check if any lines were written at all
	output = 0
}
NR == 1 {
	print $0 > OUTFILE
}

NR > 1 {
	fmtd = format($2)
	if (ge(fmtd, START_DATE) && ge(END_DATE, fmtd)) {
		output = 1
		# print "adding line " NR " " $0 
		print $0 >> OUTFILE
	}
}

END {
	# even if no lines were written, we will exit succesfully
	# rest of it will be handled by python
	
	# exit output
}
