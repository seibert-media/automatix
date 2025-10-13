testfunction () {
  echo 'Hi, I am the test function :)'
}

testfunction2 () {
  for i in $(seq 1 10);
  do
    echo $i
    sleep 10
  done
}
