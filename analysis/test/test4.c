int foo(int y){
  return y + 4;
}

int bar(int x){
  x += foo(x);
  return x + 3;
}

int main(int argc, char** argv){
  printf("%d\n", foo(atoi(argv[1])) + bar(atoi(argv[1])));
}
