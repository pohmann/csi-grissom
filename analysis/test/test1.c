int main(int argc, char** argv){
  int x = atoi(argv[1]);
  int y = atoi(argv[2]);
  while(x < y){
    if(x % 2 == 0)
      x++;
    else
      x += (y%2+1);
    printf("%d\n", x);
  }
  printf("%d %d\n", x, y);
}
